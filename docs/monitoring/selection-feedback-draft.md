# 선택 피드백 로깅 연동 — BE 전달용 Draft

이 문서는 `docs/api-contract-draft.md`/`docs/backend-integration-*.md`에 흩어져 있는 관련
변경사항을 BE 팀이 한 번에 읽고 구현할 수 있도록 모아놓은 draft다. 상세 배경/설계 근거는
`CLAUDE.md`의 `## 모니터링·데이터 기반 가중치 보정` 섹션 참고.

## 배경 (한 문단 요약)

AI 서버는 여전히 무상태이고 도메인 데이터를 저장하지 않는다. 다만 스코어링 휴리스틱(고정
가중치)을 실제 사용자 선택 데이터로 보완하기 위해, "실제로 어떤 클러스터의 사용자/팀이 어떤
후보를 선택했는가"를 별도 텔레메트리(Supabase, AI 서버 전용)에 기록하기로 했다. 이 신호를
받으려면 BE가 기존 두 엔드포인트에 필드를 조금 더 실어 보내주기만 하면 된다 — **새 엔드포인트는
없다.**

## 핵심 원칙 3가지

1. **하위 호환**: 아래 필드들은 전부 선택(optional)이다. 안 보내도 기존 흐름은 그대로 동작한다
   — 로깅만 생략된다.
2. **BE가 새로 계산할 값은 없다**: 전부 BE가 이미 갖고 있거나 이미 AI 서버가 계산해서 돌려준
   값을 그대로 재전송하는 것뿐이다.
3. **클러스터 키는 AI 서버가 계산한다**: BE는 원본 구조화 필드만 보내면 된다 — 클러스터 정의가
   나중에 바뀌어도 BE 코드를 다시 배포할 필요가 없다.

## 변경 A — 추천 응답에 `component_scores` 추가

`POST /recommendations/user-to-team`, `POST /recommendations/team-to-user` 응답의 각 추천
항목에 필드가 하나 늘었다. **AI 서버 쪽엔 이미 반영돼 있다** — 배포된 서버를 다시 호출하면 이
필드가 응답에 포함된다.

```java
public record ComponentScores(
        double similarity, double roleMatch, double deficitFit, double beginnerFit, double activityStyleMatch
) {}
public record RecommendationItem(Long candidateId, double score, String label, ComponentScores componentScores) {}
public record RecommendationResponsePayload(List<RecommendationItem> recommendations) {}
```

**BE가 할 일**: 이 값을 그냥 기존처럼 화면에 뿌리는 것 외에, 사용자가 이 후보를 선택했을 때
아래 변경 B의 `shownCandidates`로 그대로 되돌려 보낼 수 있게 **선택 시점까지 들고 있어야
한다**(추천 목록을 보여줄 때 세션/캐시에 잠깐 저장해두는 정도면 충분).

## 변경 B — 제안 요청에 `selectionContext` 추가

`POST /proposals/user-to-team`, `POST /proposals/team-to-user` 요청(`ProposalAssemblyRequest`)에
필드가 하나 늘었다.

```java
public record ShownCandidate(Long candidateId, double totalScore, ComponentScores componentScores) {}

public record SelectionContext(
        String idempotencyKey, Map<String, Object> chooserFields, List<ShownCandidate> shownCandidates
) {}

public record ProposalAssemblyRequest(
        Long userId, Long teamId, Long contestId, Long senderId, Long receiverId, Long intentId,
        double synergyScore, String candidateSummary, String targetSummary,
        SelectionContext selectionContext  // nullable
) {}
```

### 필드별 설명

- **`idempotencyKey`** (필수, `selectionContext`를 보낼 거면): 이 요청 전용으로 새로 생성하는
  UUID(`UUID.randomUUID().toString()`). **`proposalId`가 아니다** — 이 호출 시점엔 `proposalId`가
  아직 채번되기 전이다(백엔드가 응답을 저장하며 채번). 재시도 시 같은 값을 다시 보내면 AI 서버가
  중복 기록하지 않는다(멱등).
- **`chooserFields`**: 방향에 따라 다르다.
  - `USER_TO_TEAM`(사용자가 팀을 고름): `{"desired_roles": [...], "experience_level": "..."}`
    — `/intents/extract` 결과를 저장해둔 값, 또는 `/recommendations/user-to-team` 호출 시 만든
    `queryMetadata`를 그대로 재사용하면 된다.
  - `TEAM_TO_USER`(팀장이 사용자를 고름): `{"recruiting_roles": [...], "contest_field": "..."}`
    — `embedding:refresh` 응답에서 저장해둔 정규화된 값(팀의 원본 자유 텍스트가 아니라 정규화된
    값이어야 한다 — `docs/backend-integration-team-to-user.md` 주의사항 참고).
- **`shownCandidates`**: 변경 A에서 받은 랭킹 결과 전체(컴포넌트별 점수 포함)를 그대로 담는다.

### 예시 — USER_TO_TEAM

```java
var selectionContext = new SelectionContext(
        UUID.randomUUID().toString(),
        queryMetadata,  // /recommendations/user-to-team 호출 시 만든 것 재사용
        recommendationResponse.recommendations().stream()
                .map(r -> new ShownCandidate(r.candidateId(), r.score(), r.componentScores()))
                .toList()
);

var response = mateonAiRestClient.post()
        .uri("/proposals/user-to-team")
        .body(new ProposalAssemblyRequest(
                user.getId(), team.getId(), contestId, user.getId(), team.getId(), slot.getId(),
                selectedRecommendation.score(), candidateSummary, targetSummary, selectionContext))
        .retrieve()
        .body(ProposalSchema.class);
```

### 예시 — TEAM_TO_USER (`chooserFields`만 다름)

```java
var chooserFields = Map.of(
        "recruiting_roles", team.getEmbeddingMetadata().get("recruiting_roles"),
        "contest_field", team.getEmbeddingMetadata().get("contest_field")
);

var selectionContext = new SelectionContext(
        UUID.randomUUID().toString(),
        chooserFields,
        recommendationResponse.recommendations().stream()
                .map(r -> new ShownCandidate(r.candidateId(), r.score(), r.componentScores()))
                .toList()
);
```

### JSON 예시 (`/proposals/user-to-team` 요청 바디)

```json
{
  "user_id": 203,
  "team_id": 17,
  "synergy_score": 0.91,
  "candidate_summary": "React/TypeScript 경험, 초보자",
  "target_summary": "커머스 플랫폼, BE 1명 결핍",
  "selection_context": {
    "idempotency_key": "b3f1...(UUID)",
    "chooser_fields": { "desired_roles": ["BE"], "experience_level": "beginner" },
    "shown_candidates": [
      {
        "candidate_id": 17, "total_score": 0.91,
        "component_scores": { "similarity": 0.8, "role_match": 1.0, "deficit_fit": 1.0, "beginner_fit": 0.5, "activity_style_match": 1.0 }
      },
      {
        "candidate_id": 42, "total_score": 0.14,
        "component_scores": { "similarity": 0.1, "role_match": 0.0, "deficit_fit": 0.0, "beginner_fit": 1.0, "activity_style_match": 0.5 }
      }
    ]
  }
}
```

## BE 체크리스트

- [ ] `/recommendations/*` 응답 DTO에 `componentScores` 필드 추가 (역직렬화만 하면 됨, 별도 처리 불필요)
- [ ] 추천 목록을 사용자가 선택할 때까지 `componentScores`를 포함해 들고 있기
- [ ] `/proposals/*` 요청 DTO에 `selectionContext`(nullable) 추가
- [ ] 요청 전용 `idempotencyKey`(UUID) 생성 로직 추가 — `proposalId`와 혼동하지 말 것
- [ ] `chooserFields`는 이미 저장해둔 값을 방향에 맞게 넣기만 하면 됨(신규 계산 없음)
- [ ] 우선 `selectionContext` 없이 배포해도 무방 — 준비되는 대로 필드만 추가하면 그 시점부터 로깅 시작

## AI 서버 쪽 구현/검증 상태 (참고용)

AI 서버 쪽은 이미 구현하고 실제 Supabase 프로젝트에 붙여서 끝까지 검증했다(judge 판정 로그,
클러스터 선택 이벤트 기록, 멱등성, PII 자동 익명화 pg_cron 전부 실제 쓰기·읽기 테스트 완료 —
2026-08-20). BE가 위 필드들을 보내주는 시점부터 바로 데이터가 쌓인다. 질문이나 불명확한 부분은
이 문서 대신 `docs/backend-integration-user-to-team.md`(2-4-1), `docs/backend-integration-
team-to-user.md`(3-3-1), `docs/api-contract-draft.md`(6번 섹션)의 원본 설명도 함께 참고하면 된다
— 내용은 동일하고 이 문서는 그걸 한 곳에 모은 것뿐이다.
