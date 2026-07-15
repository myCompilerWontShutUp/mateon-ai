# mateon-backend 연동 가이드 — 제안 (USER_TO_TEAM)

`docs/api-contract-draft.md`가 "요청/응답 JSON이 어떤 모양인가"를 다룬다면, 이 문서는
**"백엔드 코드에서 언제, 어떻게 호출해야 하는가"**를 다룬다. 사용자가 팀을 찾는 흐름(제안)을
다룬다. mateon-backend가 Java 21 / Spring Boot 기반이므로 예시 코드도 그 기준으로 작성한다
(`RestClient`, Java record, Spring Data JPA).

**공통 전제 — AI 서버는 무상태다.** 이전 호출을 기억하지 않으므로, 뭔가 바뀔 때마다 "바뀐
부분만" 보내는 게 아니라 그 시점의 전체 상태를 통째로 다시 보낸다. `X-Internal-Secret` 헤더를
기본으로 붙인 `RestClient` 빈이 이미 있다고 가정한다(팀 임베딩 가이드의 "사전 설정" 참고).

---

## 2-1. 의도 추출 — `POST /intents/extract`

사용자가 자기소개서를 작성하거나 재질문에 답할 때마다 호출한다. **AI 서버는 대화 세션을
기억하지 않으므로, 매번 지금까지의 전체 컨텍스트(자기소개서 + 지금까지 받은 답변 전부)를
다시 보낸다.**

> 추출 프롬프트: [`prompts/user_intent_extraction.txt`](../prompts/user_intent_extraction.txt)
> 챗봇 응답 생성 프롬프트: [`prompts/user_intent_chat_reply.txt`](../prompts/user_intent_chat_reply.txt)

**첫 API 호출 전에 프론트가 먼저 인사말을 보여줘야 한다.** `messages`는 최소 1개가 필요해서
(비우면 422), 사용자가 아직 아무 말도 안 한 시점엔 API를 호출하지 않고 고정 문구를 그대로
표시한다 — AI 이름은 "드림이"로 고정:

```java
public static final String AI_PERSONA_NAME = "드림이";
public static final String OPENING_GREETING =
        "안녕! 나는 드림이야, 너한테 딱 맞는 팀을 찾아주는 도우미야. 먼저 너에 대해 간단히 "
        + "소개해줄래? 어떤 역할을 하고 싶은지, 관심 분야나 경험이 있다면 편하게 말해줘!";
```

사용자가 이 인사말에 답하면 그 답변이 `messages`의 두 번째 항목이 된다(첫 번째는 인사말
자체) — `missingFields`가 곧바로 빈 상태가 되든(즉시 추천 가능) 아니든 상관없이, 이 인사말은
항상 먼저 나온다.

```java
public record ConversationMessage(int id, String role, String message) {}  // role: "user" | "assistant"

public record IntentExtractionRequest(List<ConversationMessage> messages) {}

public record ExtractedIntentFields(
        List<String> desiredRoles, List<String> skills, List<String> interests,
        String activityGoal, String activityStyle, String experienceLevel
) {}

public record IntentExtractionResponse(
        List<String> missingFields,
        ExtractedIntentFields extracted,
        String embeddingText,
        List<Double> embeddingVector,
        String assistantMessage
) {}
```

**AI의 질문(`assistantMessage`)도 반드시 `messages`에 같이 재전송해야 한다** (2026-07-15
추가 — 실제 시뮬레이션에서 발견된 버그를 고치며 추가된 규칙). 이걸 빼고 사용자 발화만 보내면
"없는거같아"/"평범한거같은데" 같은 짧고 모호한 답변이 무엇에 대한 답인지 알 길이 없어서
`missingFields`가 영영 안 비고 같은 질문이 반복된다.

```java
// 세션에 지금까지의 메시지 리스트를 들고 있다가(user/assistant 둘 다) 매번 통째로 다시 보낸다.
List<ConversationMessage> messages = new ArrayList<>();
messages.add(new ConversationMessage(1, "assistant", openingGreetingText));
messages.add(new ConversationMessage(2, "user", selfIntroductionText));

var response = mateonAiRestClient.post()
        .uri("/intents/extract")
        .body(new IntentExtractionRequest(messages))
        .retrieve()
        .body(IntentExtractionResponse.class);

// assistantMessage를 화면에 그대로 보여주고, 동시에 messages에도 append해야 다음 호출에서
// 맥락으로 쓰인다. 재진술 + 다음 질문(하나만) 또는 추천 시작 안내가 이미 자연어로 완성돼
// 있다 — 백엔드/프론트가 missingFields를 보고 질문 문구를 직접 조립할 필요는 없다.
messages.add(new ConversationMessage(messages.size() + 1, "assistant", response.assistantMessage()));

if (!response.missingFields().isEmpty()) {
    // 사용자가 답하면 그 답변도 새 ConversationMessage(role: "user")로 messages에 append하고
    // (id는 messages.size() + 1) 다시 /intents/extract를 호출한다.
    return;
}

// missingFields가 비었으면 완성된 것 — 이 시점에 백엔드가 MatchingIntentSlot을 만들고
// intent_id를 채번해서 저장한다. embedding_vector도 함께 저장한다(AI 서버는 저장 안 함).
var slot = MatchingIntentSlot.from(userId, response);
matchingIntentSlotRepository.save(slot);
```

## 2-2. 추천 조회 — `POST /recommendations/user-to-team`

백엔드가 룰 기반으로 후보 팀을 먼저 거른 뒤(모집중/마감전/미지원 등), 그 팀들의 **DB에
저장해둔** `embedding_vector`/`metadata`를 실어서 호출한다.

```java
public record CandidateEmbeddingPayload(
        Long candidateId, List<Double> embeddingVector, Map<String, Object> metadata
) {}

public record RecommendationRequestPayload(
        List<Double> queryEmbeddingVector, Map<String, Object> queryMetadata,
        List<CandidateEmbeddingPayload> candidates
) {}

public record RecommendationItem(Long candidateId, double score, String label) {}
public record RecommendationResponsePayload(List<RecommendationItem> recommendations) {}
```

```java
List<Team> candidateTeams = teamRepository.findRecruitingTeamsFor(user); // 백엔드 룰 필터링

var candidates = candidateTeams.stream()
        .map(t -> new CandidateEmbeddingPayload(t.getId(), t.getEmbeddingVector(), t.getEmbeddingMetadata()))
        .toList();

var queryMetadata = Map.of(
        "desired_roles", slot.getDesiredRoles(),
        "skills", slot.getSkills(),
        "activity_style", slot.getActivityStyle(),
        "experience_level", slot.getExperienceLevel()
);

var response = mateonAiRestClient.post()
        .uri("/recommendations/user-to-team")
        .body(new RecommendationRequestPayload(slot.getEmbeddingVector(), queryMetadata, candidates))
        .retrieve()
        .body(RecommendationResponsePayload.class);

// response.recommendations()를 그대로 화면에 뿌린다 (team_id + score + label). 이 시점엔
// proposal_id가 없다 — 아직 사용자가 팀을 선택하지 않았다.
```

## 2-3. 상세 이유 (lazy, 선택) — `POST /recommendations/reason`

사용자가 추천 목록에서 특정 팀을 클릭했을 때만 호출한다(목록 전체에 대해 미리 호출하지 않는다
— 비용 낭비). `candidate_summary`(지원자 요약), `target_summary`(팀 요약), `score_context`
(점수 구성요소를 짧은 서술로 요약한 문자열, 예: "유사도 높음, 역할 일치")를 실어 보내면 이유
텍스트 한두 문장을 받는다.

> 생성 프롬프트: [`prompts/recommendation_reason.txt`](../prompts/recommendation_reason.txt)

## 2-4. 최종 제안 조립 — `POST /proposals/user-to-team`

사용자가 팀을 선택하면, 2-2에서 받은 해당 팀의 `score`를 그대로 재사용해서 호출한다(AI 서버가
다시 계산하지 않는다).

> 생성 프롬프트: [`prompts/user_to_team_proposal.txt`](../prompts/user_to_team_proposal.txt).
> summary/message가 설계 원칙(절대평가 금지, ID/점수 미언급 등)을 지키는지는
> `scripts/judge_outputs.py`로 점검할 수 있다.

```java
public record ProposalAssemblyRequest(
        Long userId, Long teamId, Long contestId, Long senderId, Long receiverId, Long intentId,
        double synergyScore, String candidateSummary, String targetSummary
) {}

public record ProposalSchema(
        String direction, Long userId, Long teamId, Long contestId, Long senderId, Long receiverId,
        Long intentId, double synergyScore, Double portfolioRoleFitScore, String summary, String message
) {}
```

`portfolioRoleFitScore`는 응답(`ProposalSchema`)에만 있고 요청에는 없다 — 항상 `null`로
돌아오는 예약 필드다(자세한 이유는 `docs/backend-integration-team-to-user.md` 참고).

```java
var response = mateonAiRestClient.post()
        .uri("/proposals/user-to-team")
        .body(new ProposalAssemblyRequest(
                user.getId(), team.getId(), contestId, user.getId(), team.getId(), slot.getId(),
                selectedRecommendation.score(), candidateSummary, targetSummary))
        .retrieve()
        .body(ProposalSchema.class);

// 응답엔 proposal_id가 없다 — 백엔드가 저장하며 채번한다.
Proposal proposal = Proposal.from(response);
proposalRepository.save(proposal); // 여기서 비로소 proposal_id 생성
```

## 에러 처리

- `401`: `X-Internal-Secret` 누락/오류. 재시도해도 소용없다 — 설정값을 확인해야 한다.
- `422`: 요청 바디 검증 실패(필드 누락/타입 불일치). `docs/api-contract-draft.md`와 대조해야
  한다.
- `5xx` / 타임아웃: AI 서버 내부 OpenAI 호출 실패 등. 이 엔드포인트들은 멱등하므로(같은 입력 →
  같은 결과) 안전하게 재시도할 수 있다.
