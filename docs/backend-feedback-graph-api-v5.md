# Mate-On AI 연동 API 명세서 — 선택 피드백 · 공모전 유사도 지도 (V5 수정본)

> **문서 목적**  
> BE가 AI 서버의 선택 피드백 및 공모전 유사도 지도 기능을 연동하기 위한 요청·응답 계약입니다.  
> Java 구현 예시는 포함하지 않으며, JSON 키는 모두 `snake_case`입니다.

> **공통 호출 규칙**
>
> - Content-Type: `application/json`
> - 필수 헤더: `X-Internal-Secret: {공유 시크릿}`
> - AI 서버는 요청받은 데이터로 계산만 수행합니다.
> - 아래 임베딩 벡터는 가독성을 위해 일부 값만 적었습니다. 실제 요청에는 **실수 1,536개**를 정확히 보내야 합니다.

---

## 엔드포인트 요약

| 구분 | Method | Endpoint | 설명 |
|---|---|---|---|
| 추천 결과 | `POST` | `/recommendations/user-to-team` | 사용자에게 팀을 추천하며, 선택 피드백에 재사용할 컴포넌트별 점수를 반환합니다. |
| 추천 결과 | `POST` | `/recommendations/team-to-user` | 팀에게 사용자를 추천하며, 선택 피드백에 재사용할 컴포넌트별 점수를 반환합니다. |
| 선택 피드백 | `POST` | `/selection-events` | 사용자가 실제로 선택한 후보와 당시 노출된 추천 목록을 기록 요청합니다. |
| 공모전 그래프 | `POST` | `/contests/similarity-map` | 기준 공모전과 후보 공모전의 유사도 및 방사형 그래프 좌표를 계산합니다. |

---

# 1. 추천 결과의 컴포넌트별 점수

## 1-1. 사용자 → 팀 추천

### Endpoint

`POST /recommendations/user-to-team`

### 설명

사용자 의도 임베딩과 BE가 선정한 후보 팀을 받아 상위 팀을 반환합니다.

각 추천 항목의 `component_scores`는 이후 `POST /selection-events`의
`selection_context.shown_candidates[].component_scores`에 **수정 없이 그대로 재전송**합니다.

### Request JSON

```json
{
  "query_embedding_vector": [0.0102, -0.0041, 0.0033],
  "query_metadata": {
    "desired_roles": ["BE"],
    "skills": ["Python", "FastAPI"],
    "activity_style": "체계적인 협업",
    "experience_level": "beginner",
    "activity_time": "평일 저녁"
  },
  "candidates": [
    {
      "candidate_id": 17,
      "embedding_vector": [0.0088, -0.0035, 0.0041],
      "metadata": {
        "recruiting_roles": ["BE"],
        "required_skills": ["Python", "FastAPI"],
        "activity_style": "체계적인 협업",
        "beginner_friendly": true,
        "activity_time": "평일 저녁"
      }
    }
  ]
}
```

### Response JSON — `200 OK`

```json
{
  "recommendations": [
    {
      "candidate_id": 17,
      "score": 0.92,
      "label": "BE 역할을 모집하고 있어요",
      "component_scores": {
        "similarity": 0.8,
        "role_match": 1.0,
        "deficit_fit": 1.0,
        "activity_style_match": 1.0,
        "beginner_fit": 1.0,
        "activity_time_match": 1.0
      }
    }
  ]
}
```

---

## 1-2. 팀 → 사용자 추천

### Endpoint

`POST /recommendations/team-to-user`

### 설명

팀의 결핍 임베딩과 BE가 선정한 후보 사용자를 받아 상위 사용자를 반환합니다.

응답 구조와 `component_scores`의 사용 방법은 사용자 → 팀 추천과 같습니다.

### Request JSON

```json
{
  "query_embedding_vector": [0.0102, -0.0041, 0.0033],
  "query_metadata": {
    "recruiting_roles": ["BE"],
    "required_skills": ["Python", "FastAPI"],
    "activity_style": "체계적인 협업",
    "beginner_friendly": true,
    "activity_time": "평일 저녁",
    "contest_field": "SCIENCE_ENGINEERING_TECH_IT"
  },
  "candidates": [
    {
      "candidate_id": 203,
      "embedding_vector": [0.0088, -0.0035, 0.0041],
      "metadata": {
        "desired_roles": ["BE"],
        "skills": ["Python", "FastAPI"],
        "activity_style": "체계적인 협업",
        "experience_level": "beginner",
        "activity_time": "평일 저녁"
      }
    }
  ]
}
```

### Response JSON — `200 OK`

```json
{
  "recommendations": [
    {
      "candidate_id": 203,
      "score": 0.908,
      "label": "BE 역할에 지원 가능해요",
      "component_scores": {
        "similarity": 0.77,
        "role_match": 1.0,
        "deficit_fit": 1.0,
        "activity_style_match": 1.0,
        "beginner_fit": 1.0,
        "activity_time_match": 1.0
      }
    }
  ]
}
```

### `component_scores` 설명

| 필드 | 타입 | 설명 |
|---|---:|---|
| `similarity` | number | 후보군 안에서 정규화된 임베딩 유사도 점수입니다. |
| `role_match` | number | 모집 역할과 희망 역할의 일치 점수입니다. |
| `deficit_fit` | number | 팀이 필요로 하는 스킬을 후보가 보완하는 정도입니다. |
| `activity_style_match` | number | 활동 방식의 일치 점수입니다. |
| `beginner_fit` | number | 팀의 초보자 수용 여부와 후보 경험 수준의 적합도입니다. |
| `activity_time_match` | number | 활동 시간대의 일치 점수입니다. 현재 추천 총점에는 반영하지 않지만 피드백 분석을 위해 반환합니다. |

> `component_scores`는 현재 위 6개 키를 반환합니다. BE는 값을 재계산하거나 이름을 바꾸지 않고 선택 시점까지 보관해야 합니다.

---

# 2. 선택 피드백 기록

## Endpoint

`POST /selection-events`

## 설명

추천 목록에서 실제로 선택된 후보와 선택 당시 화면에 노출된 전체 추천 결과를 기록 요청합니다.

- `/proposals/user-to-team`, `/proposals/team-to-user`와 독립된 엔드포인트입니다.
- 제안 조립 요청에는 `selection_context`를 추가하지 않습니다.
- 사용자가 후보 선택을 확정하고 제안 생성 요청이 성공한 뒤, 사용자 응답 흐름을 막지 않는 별도 호출로 전송합니다.
- `idempotency_key`가 같으면 같은 이벤트로 처리하므로 재시도할 때도 동일한 값을 사용합니다.
- 정상 인증 및 요청 검증이 끝나면 저장 완료를 기다리지 않고 즉시 `accepted: true`를 반환합니다.
- 따라서 `accepted: true`는 **저장 성공 확인이 아니라 기록 요청 접수 확인**입니다.
- 로깅 실패가 제안 생성이나 사용자 화면 흐름을 막아서는 안 됩니다.

## Request JSON — USER_TO_TEAM

```json
{
  "direction": "USER_TO_TEAM",
  "selected_candidate_id": 17,
  "selection_context": {
    "idempotency_key": "b3f14706-26d1-4d39-8458-14c3db59f238",
    "chooser_fields": {
      "desired_roles": ["BE"],
      "experience_level": "beginner"
    },
    "shown_candidates": [
      {
        "candidate_id": 17,
        "total_score": 0.92,
        "component_scores": {
          "similarity": 0.8,
          "role_match": 1.0,
          "deficit_fit": 1.0,
          "activity_style_match": 1.0,
          "beginner_fit": 1.0,
          "activity_time_match": 1.0
        }
      },
      {
        "candidate_id": 42,
        "total_score": 0.265,
        "component_scores": {
          "similarity": 0.1,
          "role_match": 0.0,
          "deficit_fit": 0.0,
          "activity_style_match": 0.5,
          "beginner_fit": 1.0,
          "activity_time_match": 0.0
        }
      }
    ]
  }
}
```

## Request JSON — TEAM_TO_USER

```json
{
  "direction": "TEAM_TO_USER",
  "selected_candidate_id": 203,
  "selection_context": {
    "idempotency_key": "aebc16f8-cfec-46de-bcf2-33a8110256c8",
    "chooser_fields": {
      "recruiting_roles": ["BE"],
      "contest_field": "SCIENCE_ENGINEERING_TECH_IT"
    },
    "shown_candidates": [
      {
        "candidate_id": 203,
        "total_score": 0.908,
        "component_scores": {
          "similarity": 0.77,
          "role_match": 1.0,
          "deficit_fit": 1.0,
          "activity_style_match": 1.0,
          "beginner_fit": 1.0,
          "activity_time_match": 1.0
        }
      }
    ]
  }
}
```

## Request 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `direction` | string | O | `USER_TO_TEAM` 또는 `TEAM_TO_USER`입니다. |
| `selected_candidate_id` | integer | O | 실제로 선택된 팀 ID 또는 사용자 ID입니다. `shown_candidates` 안의 후보 중 하나여야 합니다. |
| `selection_context` | object | O | 선택 당시의 추천 컨텍스트입니다. |
| `selection_context.idempotency_key` | string | O | 이 선택 이벤트 전용 멱등키입니다. 새 UUID 사용을 권장하며 `proposal_id`를 사용하지 않습니다. |
| `selection_context.chooser_fields` | object | X | 선택 주체의 클러스터 계산용 원본 필드입니다. 생략 시 빈 객체로 처리되지만, 정상적인 피드백 분석을 위해 위 방향별 필드를 보내야 합니다. |
| `selection_context.shown_candidates` | array | X | 화면에 노출된 추천 결과 전체입니다. 생략 시 빈 배열로 처리되지만, 정상적인 피드백 분석을 위해 전체 목록을 보내야 합니다. |
| `shown_candidates[].candidate_id` | integer | O | 추천 응답의 `candidate_id`입니다. |
| `shown_candidates[].total_score` | number | O | 추천 응답의 `score`를 그대로 넣습니다. |
| `shown_candidates[].component_scores` | object | O | 추천 응답의 `component_scores`를 그대로 넣습니다. |

## Response JSON — `200 OK`

```json
{
  "accepted": true
}
```

## 오류 응답

### `401 Unauthorized` — 공유 시크릿 불일치

```json
{
  "detail": "invalid internal secret"
}
```

### `422 Unprocessable Entity` — 필수 헤더 누락 또는 요청 형식 오류

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["header", "x-internal-secret"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

---

# 3. 공모전 유사도 지도

## Endpoint

`POST /contests/similarity-map`

## 설명

기준 공모전 1건과 BE가 선정한 후보 공모전 목록을 받아 다음 값을 계산합니다.

- 기준 공모전과 각 후보의 코사인 유사도
- 유사도 내림차순 순위 및 순위 백분위
- 방사형 그래프에 사용할 `x`, `y` 좌표
- 백분위 참고선을 그릴 `reference_rings`

AI 서버는 후보를 직접 조회하거나 공모전 임베딩을 생성·저장하지 않습니다. BE가 기준 공모전과 후보 공모전의 1,536차원 임베딩을 요청에 모두 포함해야 합니다.

## Request JSON

```json
{
  "query": {
    "id": "linkareer-325453",
    "embedding_vector": [0.0102, -0.0041, 0.0033],
    "title": "제1회 대학생 국제기구 입찰 경진대회",
    "organizer": "(사)정부조달수출진흥협회",
    "category": "CONTEST",
    "field": "EDUCATION",
    "detail_url": "https://linkareer.com/activity/325453"
  },
  "candidates": [
    {
      "id": "linkareer-328417",
      "embedding_vector": [0.0088, -0.0035, 0.0041],
      "title": "한솔그룹 AI 숏폼 공모전",
      "organizer": "한솔그룹",
      "category": "CONTEST",
      "field": "PLANNING_IDEA",
      "detail_url": "https://linkareer.com/activity/328417"
    }
  ],
  "top_n": 500
}
```

## Request 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `query` | object | O | 그래프 중심이 되는 기준 공모전입니다. |
| `query.id` | string | O | 공모전 식별자입니다. AI 서버는 의미를 해석하지 않고 응답에 그대로 반환합니다. |
| `query.embedding_vector` | number[] | O | 기준 공모전의 1,536차원 임베딩입니다. |
| `query.title` | string | O | 기준 공모전 제목입니다. |
| `query.organizer` | string 또는 null | X | 주최 기관입니다. |
| `query.category` | string 또는 null | X | 공모전 카테고리 코드입니다. |
| `query.field` | string 또는 null | X | 정규화된 공모전 분야 코드입니다. |
| `query.detail_url` | string 또는 null | X | 공모전 상세 URL입니다. URL 형식을 별도로 검증하지 않습니다. |
| `candidates` | array | O | BE가 선정한 후보 공모전 목록입니다. 빈 배열도 허용합니다. 각 항목의 구조는 `query`와 같습니다. |
| `top_n` | integer | X | 반환할 최대 후보 수입니다. 기본값은 `500`, 최솟값은 `1`입니다. |

## Response JSON — `200 OK`

```json
{
  "query": {
    "id": "linkareer-325453",
    "title": "제1회 대학생 국제기구 입찰 경진대회",
    "organizer": "(사)정부조달수출진흥협회",
    "category": "CONTEST",
    "field": "EDUCATION",
    "field_label": "교육",
    "detail_url": "https://linkareer.com/activity/325453"
  },
  "points": [
    {
      "id": "linkareer-328417",
      "title": "한솔그룹 AI 숏폼 공모전",
      "organizer": "한솔그룹",
      "category": "CONTEST",
      "field": "PLANNING_IDEA",
      "field_label": "기획/아이디어",
      "detail_url": "https://linkareer.com/activity/328417",
      "similarity": 0.615,
      "rank_percentile": 0.0,
      "radius": 2.6,
      "x": -2.737,
      "y": 0.025
    }
  ],
  "max_radius": 12.0,
  "min_radius": 2.6,
  "radial_jitter": 0.5,
  "reference_rings": [
    {
      "percentile": 0.1,
      "similarity_at_percentile": 0.615,
      "radius": 3.54
    },
    {
      "percentile": 0.3,
      "similarity_at_percentile": 0.615,
      "radius": 5.42
    },
    {
      "percentile": 0.6,
      "similarity_at_percentile": 0.615,
      "radius": 8.24
    },
    {
      "percentile": 0.9,
      "similarity_at_percentile": 0.615,
      "radius": 11.06
    }
  ],
  "candidate_pool_total": 1
}
```

## Response 필드 설명

| 필드 | 타입 | 설명 |
|---|---:|---|
| `query` | object | 기준 공모전의 표시용 정보를 그대로 반환합니다. 임베딩은 응답에 포함하지 않습니다. |
| `query.field_label` | string 또는 null | 알려진 분야 코드는 한글 라벨로 변환합니다. 알 수 없는 코드가 들어오면 현재 구현은 입력된 코드를 그대로 반환합니다. `field`가 `null`이면 `null`입니다. |
| `points` | array | 유사도가 높은 순서로 정렬된 후보입니다. 최대 `top_n`개를 반환합니다. |
| `points[].similarity` | number | 기준 공모전과 후보의 코사인 유사도입니다. 이론적 범위는 `-1.0`~`1.0`입니다. |
| `points[].rank_percentile` | number | 반환된 후보군 안의 순위 백분위입니다. `0.0`은 가장 유사한 후보, `1.0`은 가장 덜 유사한 후보입니다. 후보가 1개면 `0.0`입니다. |
| `points[].radius` | number | 순위 백분위로 계산한 기준 반지름입니다. 가장 유사한 후보는 `min_radius`, 가장 덜 유사한 후보는 `max_radius`에 대응합니다. |
| `points[].x`, `points[].y` | number | 그래프에 바로 사용할 좌표입니다. 실제 원점 거리는 `radius`를 중심으로 최대 `radial_jitter`만큼 흔들릴 수 있습니다. |
| `max_radius` | number | 기준 반지름의 최댓값입니다. 현재 `12.0`입니다. |
| `min_radius` | number | 기준 반지름의 최솟값입니다. 현재 `2.6`입니다. |
| `radial_jitter` | number | 점 겹침을 줄이기 위해 실제 좌표 반지름에 적용하는 최대 흔들림 폭입니다. 현재 `0.5`입니다. |
| `reference_rings` | array | 상위 10%, 30%, 60%, 90% 지점의 유사도와 기준 반지름입니다. 후보가 없으면 빈 배열입니다. |
| `candidate_pool_total` | integer | `top_n` 적용 전, 요청으로 받은 전체 후보 수입니다. |

> **그래프 해석 주의사항**  
> `radius`와 `x/y`는 절대 유사도 값이 아니라 후보군 안의 **상대 순위**를 기준으로 배치됩니다.  
> 따라서 서로 다른 요청의 점 간 거리를 직접 비교하면 안 됩니다. 실제 색상과 UI 표현은 FE가 `similarity` 또는 `rank_percentile`을 사용해 결정합니다.

## 빈 후보 목록 응답 예시 — `200 OK`

```json
{
  "query": {
    "id": "linkareer-325453",
    "title": "제1회 대학생 국제기구 입찰 경진대회",
    "organizer": null,
    "category": null,
    "field": null,
    "field_label": null,
    "detail_url": null
  },
  "points": [],
  "max_radius": 12.0,
  "min_radius": 2.6,
  "radial_jitter": 0.5,
  "reference_rings": [],
  "candidate_pool_total": 0
}
```

## 오류 응답

### `401 Unauthorized` — 공유 시크릿 불일치

```json
{
  "detail": "invalid internal secret"
}
```

### `422 Unprocessable Entity` — 필수 헤더 누락, 필수 필드 누락, `top_n < 1`, 또는 임베딩 차원 오류

```json
{
  "detail": [
    {
      "type": "too_short",
      "loc": ["body", "query", "embedding_vector"],
      "msg": "List should have at least 1536 items after validation, not 3",
      "input": [0.0102, -0.0041, 0.0033],
      "ctx": {
        "field_type": "List",
        "min_length": 1536,
        "actual_length": 3
      }
    }
  ]
}
```
