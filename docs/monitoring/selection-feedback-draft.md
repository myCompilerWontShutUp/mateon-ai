# 선택 피드백 로깅 연동 — BE 전달용 Draft

이 문서는 `docs/api-contract-draft.md`/`docs/backend-integration-*.md`에 흩어져 있는 관련
변경사항을 BE 팀이 한 번에 읽고 구현할 수 있도록 모아놓은 draft다. 상세 배경/설계 근거는
`CLAUDE.md`의 `## 모니터링·데이터 기반 가중치 보정` 섹션 참고.

**2026-08-23 개정 — 엔드포인트 분리.** 원래는 "새 엔드포인트는 없다"는 게 이 문서의 핵심
전제였는데, BE가 `/proposals/*`를 원래 계약(선택 필드 추가 이전 상태)으로 롤백하면서 선택
이벤트 로깅은 별도 엔드포인트로 분리해달라고 요청했다. **아래 "변경 A"(추천 응답에
`component_scores` 추가)는 그대로 유효**하고, **"변경 B"(제안 요청에 얹기)만 폐기 —
`POST /selection-events`라는 새 엔드포인트로 대체됐다.** 제안 조립(핵심 경로)과 선택 로깅
(모니터링 경로)을 요청 스키마 레벨에서도 완전히 독립시켜, 한쪽만 롤백·재배포할 수 있게 하기
위함이다.

## 배경 (한 문단 요약)

AI 서버는 여전히 무상태이고 도메인 데이터를 저장하지 않는다. 다만 스코어링 휴리스틱(고정
가중치)을 실제 사용자 선택 데이터로 보완하기 위해, "실제로 어떤 클러스터의 사용자/팀이 어떤
후보를 선택했는가"를 별도 텔레메트리(Supabase, AI 서버 전용)에 기록하기로 했다. 이 신호를
받으려면 BE가 (1) 기존 추천 응답에서 이미 받고 있는 `component_scores`를 선택 시점까지 들고
있다가 (2) 사용자가 실제로 선택했을 때 **별도 요청으로** `POST /selection-events`를 호출해주면
된다.

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

## 변경 B (2026-08-23 개정) — `POST /selection-events`로 분리

~~`POST /proposals/user-to-team`, `POST /proposals/team-to-user` 요청에 필드를 얹는 방식~~은
폐기됐다. 대신 **완전히 독립된 새 엔드포인트**를 호출한다 — `/proposals/*`는 원래 계약(아래
"기존 json")으로 그대로 두고, 선택 이벤트만 별도 요청으로 보낸다.

```java
public record ShownCandidate(Long candidateId, double totalScore, ComponentScores componentScores) {}

public record SelectionContext(
        String idempotencyKey, Map<String, Object> chooserFields, List<ShownCandidate> shownCandidates
) {}

public record SelectionEventRequest(
        String direction,  // "USER_TO_TEAM" 또는 "TEAM_TO_USER"
        Long selectedCandidateId,
        SelectionContext selectionContext
) {}
```

### 필드별 설명

- **`direction`**: 예전엔 어느 `/proposals/*` 엔드포인트를 호출했는지로 암묵적으로 정해졌는데,
  엔드포인트가 하나로 합쳐지면서 명시 필드가 됐다.
- **`selectedCandidateId`**: 예전엔 `/proposals/*` 요청의 `teamId`(USER_TO_TEAM)/`userId`
  (TEAM_TO_USER)를 그대로 재사용했다 — 이제 그 컨텍스트가 없으니 명시적으로 보내야 한다(제안
  응답의 `teamId`/`userId`를 그대로 넣으면 된다).
- **`idempotencyKey`**: 여전히 `proposalId`가 아니다 — 이 요청은 `/proposals/*`와 완전히
  독립이라 `proposalId`가 채번됐는지 여부와도 무관하다. 이 요청 전용으로 새 UUID를 생성해
  보낸다(재시도 시 같은 값을 다시 보내면 중복 기록되지 않는다).
- **`chooserFields`**/**`shownCandidates`**: 이전과 동일 — 아래 참고.
  - `USER_TO_TEAM`(사용자가 팀을 고름): `{"desired_roles": [...], "experience_level": "..."}`
    — `/intents/extract` 결과를 저장해둔 값, 또는 `/recommendations/user-to-team` 호출 시 만든
    `queryMetadata`를 그대로 재사용하면 된다.
  - `TEAM_TO_USER`(팀장이 사용자를 고름): `{"recruiting_roles": [...], "contest_field": "..."}`
    — `embedding:refresh` 응답에서 저장해둔 정규화된 값.
  - `shownCandidates`: 변경 A에서 받은 랭킹 결과 전체(컴포넌트별 점수 포함)를 그대로 담는다.

### 예시 — USER_TO_TEAM

```java
// 1) 제안은 원래 계약 그대로 호출 — selectionContext 없음
var proposal = mateonAiRestClient.post()
        .uri("/proposals/user-to-team")
        .body(new ProposalAssemblyRequest(
                user.getId(), team.getId(), contestId, user.getId(), team.getId(), slot.getId(),
                selectedRecommendation.score(), candidateSummary, targetSummary))
        .retrieve()
        .body(ProposalSchema.class);

// 2) 선택 로깅은 별도 요청 — 실패해도 사용자 흐름에 영향 없음, 응답을 굳이 기다릴 필요도 없음
var selectionContext = new SelectionContext(
        UUID.randomUUID().toString(),
        queryMetadata,  // /recommendations/user-to-team 호출 시 만든 것 재사용
        recommendationResponse.recommendations().stream()
                .map(r -> new ShownCandidate(r.candidateId(), r.score(), r.componentScores()))
                .toList()
);
mateonAiRestClient.post()
        .uri("/selection-events")
        .body(new SelectionEventRequest("USER_TO_TEAM", team.getId(), selectionContext))
        .retrieve()
        .toBodilessEntity();
```

### 예시 — TEAM_TO_USER (`chooserFields`/`direction`/`selectedCandidateId`만 다름)

```java
var chooserFields = Map.of(
        "recruiting_roles", team.getEmbeddingMetadata().get("recruiting_roles"),
        "contest_field", team.getEmbeddingMetadata().get("contest_field")
);
var selectionContext = new SelectionContext(
        UUID.randomUUID().toString(), chooserFields,
        recommendationResponse.recommendations().stream()
                .map(r -> new ShownCandidate(r.candidateId(), r.score(), r.componentScores()))
                .toList()
);
mateonAiRestClient.post()
        .uri("/selection-events")
        .body(new SelectionEventRequest("TEAM_TO_USER", user.getId(), selectionContext))
        .retrieve()
        .toBodilessEntity();
```

### JSON 예시 (`POST /selection-events` 요청 바디)

```json
{
  "direction": "USER_TO_TEAM",
  "selected_candidate_id": 17,
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

응답은 `{ "accepted": true }` 고정 — Supabase 기록이 실제로 성공했는지와 무관하게 항상
반환된다(fire-and-forget, 응답을 기다릴 필요도 없다).

## BE 체크리스트

- [ ] `/recommendations/*` 응답 DTO에 `componentScores` 필드 추가 (역직렬화만 하면 됨, 별도 처리 불필요)
- [ ] 추천 목록을 사용자가 선택할 때까지 `componentScores`를 포함해 들고 있기
- [ ] `/proposals/*` 요청은 **원래 계약 그대로 유지**(`selectionContext` 필드 없음 — 이미 롤백
      완료했다면 추가 작업 불필요)
- [ ] `POST /selection-events` 호출 추가 — 제안 생성 성공 직후, 별도 요청으로
- [ ] 요청 전용 `idempotencyKey`(UUID) 생성 로직 — `proposalId`와 혼동하지 말 것
- [ ] `direction`/`selectedCandidateId`를 명시적으로 채우기(예전엔 `/proposals/*` 쪽 필드에서
      암묵적으로 가져왔던 값)
- [ ] 우선 `/selection-events` 호출 없이 배포해도 무방 — 준비되는 대로 호출을 추가하면 그
      시점부터 로깅 시작(다른 엔드포인트와 마찬가지로 이 호출도 필수가 아니다)

## AI 서버 쪽 구현/검증 상태 (참고용)

핵심 로깅 로직(`app/features/quality/selection_log.py`)은 그대로다 — 2026-08-20에 이미 실제
Supabase 프로젝트에 붙여서 끝까지 검증했다(클러스터 선택 이벤트 기록, 멱등성, PII 자동 익명화
pg_cron 전부 실제 쓰기·읽기 테스트 완료). 2026-08-23에 바뀐 건 **어느 엔드포인트가 이 로직을
호출하느냐**뿐이다 — `app/features/quality/router.py`(`POST /selection-events`)로 옮기고,
`/proposals/*`(`app/features/{user_to_team,team_to_user}/proposal.py`)에서는 호출을 뺐다.
단위·엔드포인트 테스트(`tests/test_selection_event_endpoint.py`,
`tests/test_user_to_team_proposal.py`, `tests/test_team_to_user_proposal.py`)로 롤백·분리
둘 다 검증했다. BE가 `/selection-events` 호출을 추가하는 시점부터 바로 데이터가 쌓인다.
질문이나 불명확한 부분은 이 문서 대신 `docs/api-contract-draft.md`(11번 섹션)의 원본 설명도
함께 참고하면 된다 — 내용은 동일하고 이 문서는 그걸 한 곳에 모은 것뿐이다.
