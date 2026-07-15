# mateon-backend 연동 가이드 — 역제안 (TEAM_TO_USER)

`docs/api-contract-draft.md`가 "요청/응답 JSON이 어떤 모양인가"를 다룬다면, 이 문서는
**"백엔드 코드에서 언제, 어떻게 호출해야 하는가"**를 다룬다. 팀장이 사람을 찾는 흐름(역제안)을
다룬다. mateon-backend가 Java 21 / Spring Boot 기반이므로 예시 코드도 그 기준으로 작성한다
(`RestClient`, Java record, Spring Data JPA).

**공통 전제 — AI 서버는 무상태다.** 이전 호출을 기억하지 않으므로, 뭔가 바뀔 때마다 "바뀐
부분만" 보내는 게 아니라 그 시점의 전체 상태를 통째로 다시 보낸다. `X-Internal-Secret` 헤더를
기본으로 붙인 `RestClient` 빈이 이미 있다고 가정한다(팀 임베딩 가이드의 "사전 설정" 참고).

---

## 3-1. 추천 조회 — `POST /recommendations/team-to-user`

팀장이 역제안을 실행하면, 백엔드가 룰 기반으로 후보 사용자를 먼저 거른 뒤(팀 찾기 ON, 미거절,
무소속, 학교 조건 등) 호출한다. **`query_embedding_vector`는 새로 계산하지 않고, "팀 임베딩"
가이드에서 이미 저장해둔 그 팀의 `embedding_vector`를 그대로 재사용한다.**

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
Team team = teamRepository.findById(teamId).orElseThrow();
List<MatchingIntentSlot> candidateSlots = matchingIntentSlotRepository.findCandidatesFor(team); // 룰 필터링

var candidates = candidateSlots.stream()
        .map(s -> new CandidateEmbeddingPayload(s.getUserId(), s.getEmbeddingVector(), Map.of(
                "desired_roles", s.getDesiredRoles(),
                "skills", s.getSkills(),
                "experience_level", s.getExperienceLevel(),
                "activity_style", s.getActivityStyle()
        )))
        .toList();

var queryMetadata = Map.of(
        "recruiting_roles", team.getRecruitingRoles(),
        "required_skills", team.getRequiredSkills(),
        "activity_style", team.getEmbeddingMetadata().get("activity_style"),
        "beginner_friendly", team.getEmbeddingMetadata().get("beginner_friendly")
);

var response = mateonAiRestClient.post()
        .uri("/recommendations/team-to-user")
        .body(new RecommendationRequestPayload(team.getEmbeddingVector(), queryMetadata, candidates))
        .retrieve()
        .body(RecommendationResponsePayload.class);

// response.recommendations()의 candidateId는 user_id다.
```

## 3-2. 상세 이유 (lazy, 선택) — `POST /recommendations/reason`

제안 쪽과 완전히 같은 엔드포인트·같은 방식이다. `direction` 구분 없이 `candidate_summary`
(스카우트 대상 요약), `target_summary`(팀 요약), `score_context`(점수 구성요소를 짧은 서술로
요약한 문자열)만 넘기면 된다.

> 생성 프롬프트: [`prompts/recommendation_reason.txt`](../prompts/recommendation_reason.txt)

## 3-3. 최종 역제안 조립 — `POST /proposals/team-to-user`

팀장이 사용자를 선택하면, 3-1에서 받은 `score`를 `synergyScore`로 넘겨서 호출한다. 요청/응답
DTO는 제안(USER_TO_TEAM) 쪽과 완전히 동일한 `ProposalAssemblyRequest`/`ProposalSchema`를 쓴다.

> 생성 프롬프트: [`prompts/team_to_user_proposal.txt`](../prompts/team_to_user_proposal.txt).
> summary/message가 설계 원칙을 지키는지는 `scripts/judge_outputs.py`로 점검할 수 있다.

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

```java
var response = mateonAiRestClient.post()
        .uri("/proposals/team-to-user")
        .body(new ProposalAssemblyRequest(
                selectedUser.getId(), team.getId(), contestId, team.getId(), selectedUser.getId(), null,
                selectedRecommendation.score(), candidateSummary, targetSummary))
        .retrieve()
        .body(ProposalSchema.class);

Proposal proposal = Proposal.from(response); // direction: TEAM_TO_USER
proposalRepository.save(proposal);
```

**주의**: `portfolioRoleFitScore`는 응답에 필드만 남아있고 항상 `null`이다. 포트폴리오
데이터 없이 `experience_level`을 대리 지표로 쓰던 이전 방식은 신호가 약해 계산에서
뺐다(스코어링은 유사도/역할 일치도/결핍 보완도/활동 방식 일치도/초보자 적합도만 사용,
제안(USER_TO_TEAM)과 동일 구조). 실제 포트폴리오 데이터 소스가 백엔드에 생기면 이 필드를
다시 채우는 방향으로 바뀔 수 있다.

## 에러 처리

- `401`: `X-Internal-Secret` 누락/오류. 재시도해도 소용없다 — 설정값을 확인해야 한다.
- `422`: 요청 바디 검증 실패(필드 누락/타입 불일치). `docs/api-contract-draft.md`와 대조해야
  한다.
- `5xx` / 타임아웃: AI 서버 내부 OpenAI 호출 실패 등. 이 엔드포인트들은 멱등하므로(같은 입력 →
  같은 결과) 안전하게 재시도할 수 있다.
