# Mate-On AI 연동 API 명세서 — 협업 필터링·행동 기반 개인화 (V8)

> **문서 목적**
> 추천 품질 개선을 위해 새로 추가된 두 신호(사용자 행동 이력, 공모전 간 협업 필터링)를 BE가
> 연동하기 위한 명세다. V7(공모전 임베딩·유사도 지도)에서 이어지며, 그 문서의 엔드포인트는
> 변경되지 않았다.
> Java 구현 예시는 포함하지 않으며, JSON 키는 모두 `snake_case`다.

> **공통 호출 규칙**
>
> - Content-Type: `application/json`
> - 필수 헤더: `X-Internal-Secret: {공유 시크릿}`
> - **아래 필드는 전부 선택(optional)이다.** 안 보내면 기존과 완전히 동일하게 동작하므로,
>   BE가 준비되는 순서대로 하나씩 붙여도 된다.

---

## 요약 — BE가 해야 할 일

| # | 작업 | 대상 엔드포인트 | 필수 여부 |
|---|---|---|---|
| 1 | 사용자별 행동 임베딩 저장·전달 | `POST /recommendations/user-to-team` | 선택 |
| 2 | 상호작용한 공모전 ID 목록 전달 | `POST /recommendations/*` | 선택 |
| 3 | 후보 팀이 속한 공모전 ID 전달 | `POST /recommendations/user-to-team` | 선택 |
| 4 | 배치용 상호작용 이력 조회 엔드포인트 제공 | *(BE가 신설)* | CF 활성화에 필요 |

---

# 1. 행동 기반 개인화 (`/recommendations/user-to-team`)

## 설명

사용자가 북마크·지원한 공모전들의 임베딩 평균을 함께 보내면, AI 서버가 이번 검색의 의도
임베딩과 섞어 개인화한다. **협업 필터링이 아니라 콘텐츠 기반 개인화다** — 다른 사용자의 행동은
개입하지 않는다.

- 섞는 비율(α)은 **AI 서버가 결정한다.** BE는 벡터와 건수만 보내면 된다.
- 이력이 쌓일수록 행동 쪽 비중이 커지되, **의도가 절반 아래로 내려가지 않는다** — 사용자가
  이번 검색에서 직접 말한 조건이 과거 이력에 묻히면 안 되기 때문이다.
- `interaction_count`가 `0`이거나 벡터를 안 보내면 기존 동작과 **100% 동일**하다.

## 추가되는 요청 필드

```json
{
  "query_embedding_vector": [0.0102, -0.0041, 0.0033],
  "query_metadata": { "desired_roles": ["BE"], "experience_level": "beginner" },
  "candidates": [ "...(기존과 동일)" ],

  "behavior_embedding_vector": [0.0088, -0.0035, 0.0041],
  "interaction_count": 7
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `behavior_embedding_vector` | number[] 또는 null | X | 사용자가 상호작용한 공모전 임베딩의 평균. 1,536차원. |
| `interaction_count` | integer | X | 위 평균을 만든 상호작용 건수. 기본값 `0`. |

## BE 구현 방법

1. `user` 테이블에 1,536차원 벡터 컬럼과 카운트 컬럼을 추가한다.
2. 사용자가 공모전을 북마크·지원할 때, **누적 평균**으로 갱신한다 (전체 재계산 불필요):

   ```
   new_avg = (old_avg × n + new_event_vector) / (n + 1)
   ```

   `new_event_vector`는 V7의 `POST /internal/contests/embedding:refresh`로 이미 저장해둔
   공모전 임베딩을 그대로 쓰면 된다.
3. 추천 요청 시 위 두 필드를 실어 보낸다.

---

# 2. 협업 필터링 (`/recommendations/user-to-team`, `/recommendations/team-to-user`)

## 설명

"같은 사람들이 어떤 공모전을 함께 봤는가"로 공모전 간 연관도를 만들고, 그 신호를 추천 점수에
반영한다. **텍스트를 전혀 보지 않는다** — 의미 임베딩이 구조적으로 잡아내지 못하는 연관성
(예: 디자인 공모전과 사회참여 공모전을 함께 보는 집단)을 찾기 위한 별도 축이다.

- 응답의 `component_scores`에 **`cf_affinity` 키가 추가**된다.
- 동시발생 데이터가 없으면 모든 후보가 `0.0`을 받고, 이때 **순위는 기존과 수학적으로 동일**하다.
- 팀이 아니라 **공모전 단위**로 계산한다 — 팀은 모집이 끝나면 사라져 상호작용이 쌓일 시간이
  없기 때문이다.

## 추가되는 요청 필드 (기존 열린 `metadata` dict에 키만 추가하면 된다)

**USER_TO_TEAM**

```json
{
  "query_metadata": {
    "desired_roles": ["BE"],
    "interacted_event_ids": [337930, 325453]
  },
  "candidates": [
    {
      "candidate_id": 17,
      "embedding_vector": ["...1536개"],
      "metadata": { "recruiting_roles": ["BE"], "event_id": 328417 }
    }
  ]
}
```

**TEAM_TO_USER** (방향만 반대, 구조는 대칭)

```json
{
  "query_metadata": {
    "recruiting_roles": ["BE"],
    "event_id": 328417
  },
  "candidates": [
    {
      "candidate_id": 203,
      "embedding_vector": ["...1536개"],
      "metadata": { "desired_roles": ["BE"], "interacted_event_ids": [337930, 325453] }
    }
  ]
}
```

| 위치 | 필드 | 타입 | 설명 |
|---|---|---:|---|
| `query_metadata` (USER_TO_TEAM) | `interacted_event_ids` | integer[] | 사용자가 북마크·지원한 공모전 ID 목록 |
| `candidates[].metadata` (USER_TO_TEAM) | `event_id` | integer | 이 팀이 속한 공모전 ID |
| `query_metadata` (TEAM_TO_USER) | `event_id` | integer | 이 팀이 속한 공모전 ID |
| `candidates[].metadata` (TEAM_TO_USER) | `interacted_event_ids` | integer[] | 후보 사용자가 상호작용한 공모전 ID 목록 |

**요청 스키마 자체는 바뀌지 않는다** — `query_metadata`와 `metadata`는 원래 자유 dict라 키만
추가하면 된다.

## 응답 변화

```json
{
  "recommendations": [
    {
      "candidate_id": 17,
      "score": 0.54875,
      "label": "비슷한 공모전을 찾아본 사람들이 함께 관심을 보인 팀이에요",
      "component_scores": {
        "similarity": 0.8,
        "role_match": 0.0,
        "deficit_fit": 0.0,
        "activity_style_match": 0.5,
        "beginner_fit": 1.0,
        "cf_affinity": 0.62,
        "activity_time_match": 0.5
      }
    }
  ]
}
```

**주의**: `component_scores`에 키가 하나 늘었다. BE가 고정 필드 Java record로 역직렬화 중이면
`cfAffinity` 필드를 추가해야 한다(`Map<String, Double>`을 쓰고 있다면 조치 불필요). 이 값은
`POST /selection-events`의 `shown_candidates[].component_scores`로 **그대로 되돌려 보내면**
된다.

`label`도 CF가 추천 근거일 때 그 사실을 드러내는 문구로 나온다. 위 예시처럼 역할·스킬이 맞지 않고
CF 점수만 있을 때다 — 역할이나 스킬이 맞으면 그쪽이 라벨 근거가 된다.

USER_TO_TEAM은 사용자가 상호작용한 공모전과 후보 팀 공모전 사이의 쌍만 Supabase에서 읽는다. 조회가
몇 초 안에 끝나지 않거나 실패하면 CF 점수 0으로 그대로 응답한다(순위는 CF 없는 결과와 같다).

---

# 3. 배치용 상호작용 이력 조회 *(BE 신설 필요)*

CF는 전역 상호작용 행렬이 있어야 성립하므로, AI 서버의 오프라인 배치가 이력을 읽을 경로가
필요하다.

```
GET /api/internal/interactions?since=2026-08-01
X-Internal-Secret: {공유 시크릿}

→ [
    { "user_id": 12, "event_id": 337930 },
    { "user_id": 12, "event_id": 325453 },
    { "user_id": 34, "event_id": 337930 }
  ]
```

- **라이브 경로가 아니다.** 사람이 주 1회~월 1회 수동 실행하는 배치가 호출하므로 성능 부담이
  없다.
- 북마크·지원·수락 어느 것이든 "관심을 보인 행위"로 함께 넣으면 된다. 같은 사용자가 같은
  공모전에 여러 번 등장해도 AI 서버가 1회로 정규화한다.
- `since` 파라미터는 선택이다 — 전량을 매번 보내도 무방한 규모다.

이 엔드포인트가 준비되기 전까지 `cf_affinity`는 항상 `0.0`이고, 순위는 기존과 동일하다.

---

## BE 체크리스트

- [ ] `user` 테이블에 행동 임베딩 벡터 + 상호작용 카운트 컬럼 추가
- [ ] 북마크·지원 시 누적 평균으로 행동 임베딩 갱신
- [ ] `/recommendations/user-to-team` 요청에 `behavior_embedding_vector`/`interaction_count` 추가
- [ ] `query_metadata.interacted_event_ids`, `candidates[].metadata.event_id` 추가
- [ ] `component_scores` 역직렬화에 `cf_affinity` 반영 (고정 record를 쓰는 경우)
- [ ] `GET /api/internal/interactions` 신설
- [ ] 위 항목들은 **서로 독립**이라 준비되는 순서대로 하나씩 붙여도 된다
