# Mate-On AI 연동 API 명세서 — 공모전 임베딩 · 유사도 지도 (V7)

> **문서 목적**  
> 이번에 새로 추가된 공모전 임베딩 계산 엔드포인트와, 그 임베딩을 사용하는 공모전 유사도
> 지도 엔드포인트의 요청·응답 계약입니다. V5(추천/선택 피드백)에서 이 두 엔드포인트만 뽑아
> 갱신한 문서라 나머지 엔드포인트는 다루지 않습니다(V6은 건너뜁니다).  
> Java 구현 예시는 포함하지 않으며, JSON 키는 모두 `snake_case`입니다.

> **공통 호출 규칙**
>
> - Content-Type: `application/json`
> - 필수 헤더: `X-Internal-Secret: {공유 시크릿}`
> - AI 서버는 요청받은 데이터로 계산만 수행하고 아무것도 저장하지 않습니다(무상태).
> - 아래 임베딩 벡터는 가독성을 위해 일부 값만 적었습니다. 실제 요청/응답에는 **실수 1,536개**를 정확히 주고받아야 합니다.

---

## 엔드포인트 요약

| 구분 | Method | Endpoint | 설명 |
|---|---|---|---|
| 공모전 임베딩 | `POST` | `/internal/contests/embedding:refresh` | **(신규)** 공모전 제목·설명으로 임베딩 벡터를 계산합니다. |
| 공모전 그래프 | `POST` | `/contests/similarity-map` | 기준 공모전과 후보 공모전의 유사도 및 방사형 그래프 좌표를 계산합니다. |

---

# 1. 공모전 임베딩 계산 (신규)

## Endpoint

`POST /internal/contests/embedding:refresh`

## 설명

공모전 하나의 제목과 설명을 받아 임베딩 벡터를 계산해서 반환합니다.

- AI 서버는 이 벡터를 저장하지 않습니다 — 계산 결과만 반환하며, **저장은 BE가** 합니다.
- `event_id`는 AI 서버가 의미를 해석하거나 검증하지 않고 응답에 그대로 돌려줍니다 — 어떤
  요청에 대한 결과인지 BE가 구분할 수 있게 하기 위한 echo일 뿐입니다.
- 공모전 등록/수정 시(제목이나 설명이 바뀔 때) 호출합니다. 기존에 이미 등록된 공모전을
  일괄로 채워 넣어야 한다면 이 엔드포인트를 공모전 수만큼 반복 호출하면 됩니다(한 번의
  요청은 한 건만 처리합니다).
- 아래 `/contests/similarity-map`에 넘길 `embedding_vector`가 바로 이 응답의
  `embedding_vector`입니다.

## Request JSON

```json
{
  "event_id": 337930,
  "title": "경기도 1인가구 정책제안 아이디어 공모전",
  "description": "경기도 1인가구의 삶의 질 향상을 위한 정책 아이디어를 공모합니다. 참여 대상: 경기도 거주 청년..."
}
```

## Request 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|---|---:|:---:|---|
| `event_id` | integer | O | BE가 관리하는 공모전 ID입니다. 응답에 그대로 echo됩니다. |
| `title` | string | O | 공모전 제목입니다. |
| `description` | string | O | 공모전 설명입니다. 요약 여부와 무관하게 갖고 있는 설명 텍스트를 그대로 보내면 됩니다. |

## Response JSON — `200 OK`

```json
{
  "event_id": 337930,
  "embedding_vector": [0.0102, -0.0041, 0.0033]
}
```

## Response 필드 설명

| 필드 | 타입 | 설명 |
|---|---:|---|
| `event_id` | integer | 요청으로 받은 `event_id`를 그대로 반환합니다. |
| `embedding_vector` | number[] | 1,536차원 임베딩 벡터입니다. |

## 오류 응답

### `401 Unauthorized` — 공유 시크릿 불일치

```json
{
  "detail": "invalid internal secret"
}
```

### `422 Unprocessable Entity` — 필수 헤더 누락 또는 필수 필드 누락

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "title"],
      "msg": "Field required",
      "input": {"event_id": 337930, "description": "..."}
    }
  ]
}
```

---

# 2. 공모전 유사도 지도

## Endpoint

`POST /contests/similarity-map`

## 설명

기준 공모전 1건과 BE가 선정한 후보 공모전 목록을 받아 다음 값을 계산합니다.

- 기준 공모전과 각 후보의 코사인 유사도
- 유사도 내림차순 순위 및 순위 백분위
- 방사형 그래프에 사용할 `x`, `y` 좌표
- 백분위 참고선을 그릴 `reference_rings`

AI 서버는 후보를 직접 조회하거나 공모전 임베딩을 자체적으로 생성·저장하지 않습니다 —
**AI 서버 내부에 캐싱된 임베딩을 쓰는 게 아니라, 이 요청에 실려온 `embedding_vector`만
그대로 씁니다.** BE가 기준 공모전과 후보 공모전의 1,536차원 임베딩(위 1번 엔드포인트로
미리 계산해서 저장해둔 값)을 요청에 모두 포함해야 합니다.

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
