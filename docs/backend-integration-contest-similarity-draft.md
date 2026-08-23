# 공모전 유사도 지도 — BE 전달용 Draft

이 문서는 새 엔드포인트 `POST /contests/similarity-map`을 BE 팀이 한 번에 읽고 연동할 수
있도록 정리한 draft다. 요청/응답 JSON 예시는 `docs/api-contract-draft.md`(10번 섹션)에도
동일하게 있다 — 이 문서는 배경과 설계 이유, 체크리스트를 더 자세히 담는다.

## 배경 (한 문단 요약)

AI 서버가 시연용으로 만들었던 "공모전 유사도 지도"(쿼리 공모전 1건을 중심에 두고, 비슷한
공모전은 가깝게·안 비슷한 공모전은 멀게 배치하는 방사형 시각화)를 실제 엔드포인트로 승격했다.
핵심 매칭 기능(제안/역제안)과는 무관한 **부가 시각화 기능**이며, 다른 엔드포인트와 동일하게
무상태다 — AI 서버는 계산만 하고 아무것도 저장하지 않는다.

## 핵심 원칙 3가지

1. **새 엔드포인트 하나뿐**: `POST /contests/similarity-map`. 기존 엔드포인트 변경 없음.
2. **후보 선정은 여전히 BE 책임**: AI 서버는 `candidates`로 받은 것 안에서만 유사도를 계산·
   정렬·`top_n` 컷을 한다. 몇 건을 후보로 넣을지는 BE가 결정한다.
3. **AI 서버는 공모전 임베딩을 계산하지 않는다** — 이 엔드포인트는 **이미 계산된**
   `embedding_vector`(1536차원, `text-embedding-3-small`)를 요청에 실어 받는 것을 전제로
   한다. **공모전 임베딩 자체를 어디서/언제 계산할지는 아직 미정이다** — 아래 "미확정 사항"
   참고. 지금 당장은 AI 서버 쪽 시연·테스트용으로 로컬 캐시(`data/contest_embeddings_cache.json`)
   에 미리 계산해둔 값을 썼다.

## 요청 — `POST /contests/similarity-map`

```java
public record ContestSimilarityItem(
        String id, List<Double> embeddingVector, String title,
        String organizer, String category, String field, String detailUrl
) {}

public record ContestSimilarityRequest(
        ContestSimilarityItem query, List<ContestSimilarityItem> candidates, Integer topN
) {}
```

- **`id`**: 공모전 식별자(예: `externalId`). AI 서버는 이 값을 그대로 echo만 한다 — 의미를
  해석하지 않는다.
- **`embedding_vector`**: 1536차원 아니면 `422`.
- **`title`/`organizer`/`category`/`detail_url`**: 응답에 그대로 echo되는 표시용 메타데이터.
- **`field`**: 정규화된 `ContestField` 코드(21개, `docs/api-contract-draft.md` 참고)를 기대한다.
  코드가 아닌 값이 와도 에러는 안 나고, 그 값 그대로 echo하되 `field_label`만 못 붙인다(원문을
  안 보존하는 실패보다 낫다고 판단).
- **`top_n`**: 기본 500. `candidates`가 이보다 적으면 그냥 전부 쓴다.

## 응답

```java
public record ContestSimilarityPoint(
        String id, String title, String organizer, String category, String field,
        String fieldLabel, String detailUrl, double similarity, double rankPercentile,
        double radius, double x, double y
) {}

public record ContestSimilarityReferenceRing(
        double percentile, double similarityAtPercentile, double radius
) {}

public record ContestSimilarityResponse(
        ContestSimilarityQueryEcho query, List<ContestSimilarityPoint> points,
        double maxRadius, double minRadius, double radialJitter,
        List<ContestSimilarityReferenceRing> referenceRings, int candidatePoolTotal
) {}
```

### 반지름은 절대 유사도가 아니라 순위 백분위로 정해진다

처음엔 `radius = 최대반지름 × (1 - similarity)`처럼 절대 유사도(0~1)를 그대로 반지름에
매핑했다. 그런데 실제 공모전 데이터는 유사도가 0.25~0.62 같은 좁은 대역에만 몰려 있어서
(공모전끼리는 애초에 서로 크게 다른 주제를 다루는 경우가 많아 유사도 자체가 높게 안 나옴),
"유사도 0.9" 기준선 안쪽엔 점이 하나도 안 찍히고 전부 바깥쪽 절반에만 몰려 보이는 문제가
실측으로 나왔다.

그래서 `radius`(그리고 `x`/`y`)는 **`candidates` 안에서의 상대 순위**로 정한다 — 가장 유사한
후보가 항상 `min_radius`, 가장 안 비슷한 후보가 항상 `max_radius`에 오도록 전체 구간을 채운다.
**절대 유사도 숫자와 반지름의 직접적인 대응은 없다** — "유사도 0.9면 이 정도 거리"라는 해석은
성립하지 않는다. 대신 `reference_rings`가 "상위 10%가 지금 후보군 기준으로 실제 어떤 유사도
값에 해당하는지"를 같이 내려준다 — FE가 참고선에 절대 유사도 숫자를 라벨로 보여줄 수 있게.

### 같은 순위대끼리만 흩어지고, 다른 순위대는 절대 안 겹친다

`x`/`y`는 "자기 순위가 정한 이상적인 반지름 ± `radial_jitter`" 범위에서만 무작위로 흔든
좌표다 — 완전히 무의미한 난수는 아니고, 비슷한 순위끼리만 자연스럽게 뭉치지 않고 흩어져
보이게 하는 용도다. 처음엔 모든 점이 반지름 범위(안쪽 경계)를 공유하는 방식으로 만들었는데,
그러면 유사도가 낮은 점도 우연히 중앙 근처로 뽑힐 수 있어서 — 실제로 시연 중 그 버그가
재현돼서 — 지금 방식(순위별로 반지름 범위 자체가 겹치지 않음)으로 고쳤다.

### 색상은 응답에 없다

`similarity`/`rank_percentile`만 내려준다. 실제로 화면에 어떤 색(예: 멀수록 회색·가까울수록
파랑)을 칠할지는 FE가 계산한다 — 라이트/다크 테마에 따라 색이 달라져야 하고, 색 팔레트는
프레젠테이션 관심사라 AI 서버가 매번 정할 이유가 없다.

## BE 체크리스트

- [ ] `POST /contests/similarity-map` 호출 준비 — 다른 엔드포인트와 동일하게
      `X-Internal-Secret` 헤더 필요
- [ ] 쿼리 공모전과 후보 공모전들의 `embedding_vector`(1536차원)를 준비 — **AI 서버는 이 값을
      계산해주지 않는다.** 아래 "미확정 사항" 확인 필요
- [ ] 후보 선정(1차 필터링) — 몇 건을 `candidates`로 보낼지 결정. `top_n`(기본 500)보다 후보가
      많아도 AI 서버가 유사도 상위 `top_n`건만 골라 계산하니, 넉넉히 보내도 무방
- [ ] 응답의 `x`/`y`/`radius`/`reference_rings`를 FE 시각화 컴포넌트에 그대로 전달(AI 서버 →
      BE → FE, BE가 프론트와 직접 붙는 구조는 없음 — 기존 그래프 시각화와 같은 원칙)

## 미확정 사항 — BE와 조율 필요

**공모전 임베딩을 어디서/언제 계산할지가 아직 안 정해졌다.** 팀 임베딩은
`POST /internal/teams/embedding:refresh`가 팀 생성/수정 시점에 미리 계산해두는 구조가 이미
있는데, 공모전은 이런 갱신 훅이 아직 없다. 다음 중 하나를 정해야 한다:

1. 공모전용 `embedding:refresh` 류 엔드포인트를 팀과 같은 패턴으로 새로 만든다(공모전
   생성/수정 시 BE가 호출 → AI 서버가 `embedding_text`/`embedding_vector`/`metadata` 계산해
   반환 → BE가 저장).
2. 아니면 BE가 이미 다른 경로로 공모전 임베딩을 들고 있다면 그걸 그대로 쓴다.

이 결정 전까지는 AI 서버 쪽 시연·테스트에서 쓴 방식(로컬에서 한 번에 계산해 캐싱)으로 대체할
수 없다 — 실제 서비스에서는 매 요청마다 최신 벡터가 필요하다.

## AI 서버 쪽 구현·검증 상태 (참고용)

`app/features/contest_similarity/`(service.py, router.py) + `app/schemas/contest_similarity.py`로
구현 완료, 단위 테스트(`tests/test_contest_similarity_service.py`,
`tests/test_contest_similarity_endpoint.py`)로 검증했다 — 반지름 순위 매핑, 순위대 간 겹침 없음
(회귀 테스트), `field_label` 파생, 인증 헤더, 벡터 차원 검증까지 포함. OpenAI 호출이 전혀 없는
순수 계산 엔드포인트라 비용·지연 걱정도 없다. BE가 위 미확정 사항(임베딩 소스)만 정하면 바로
연동 가능한 상태다.
