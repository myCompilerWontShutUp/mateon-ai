"""Hit@K / NDCG@K — 오프라인 평가(2번 항목)에서 4개 랭킹 방법을 비교하는 데 쓰는 지표.

복수 정답(여러 team_id가 동시에 "정답")을 허용하기로 했는데, 복수 정답 + Hit@K(이진 지표)만
쓰면 여러 방법론의 점수가 쉽게 포화돼(다들 100%에 가까워짐) 변별력이 떨어진다 — 그래서 순위에
민감한 NDCG@K를 같이 본다(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 3번 참고).
"""

import math
from collections.abc import Sequence


def hit_at_k(ranked_ids: Sequence, relevant_ids: set, k: int) -> float:
    """상위 k개 안에 정답이 하나라도 있으면 1.0, 없으면 0.0."""
    if not relevant_ids:
        return 0.0
    return 1.0 if set(ranked_ids[:k]) & relevant_ids else 0.0


def ndcg_at_k(ranked_ids: Sequence, relevant_ids: set, k: int) -> float:
    """이진 관련성(정답 집합에 속하면 1, 아니면 0) 기준 NDCG@k."""
    if not relevant_ids:
        return 0.0

    dcg = sum(
        1.0 / math.log2(rank + 2)  # rank는 0-indexed, log2(1+1)부터 시작
        for rank, candidate_id in enumerate(ranked_ids[:k])
        if candidate_id in relevant_ids
    )

    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(rank + 2) for rank in range(ideal_hits))
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def graded_ndcg_at_k(ranked_ids: Sequence, relevance: dict, k: int) -> float:
    """관련성이 이진(0/1)이 아니라 연속값(예: 시뮬레이션한 "진짜 선호" 점수)일 때의 NDCG@k.

    `ndcg_at_k`(정답 집합 전체를 동등하게 취급)와 달리, 정답 중에서도 어떤 걸 더 위로 올렸는지를
    평가한다 — CLAUDE.md 모니터링 섹션에서 지적한 대로, LLM 정답 기준 NDCG는 프로덕션
    스코어링과 정답 라벨링 기준이 비슷해 포화되는 문제가 있어, 보정모델이 실제로 겨냥하는
    "가상의 진짜 선호"(app/evaluation/simulation.py) 기준으로 별도 계산한다.
    """
    if not relevance or all(v <= 0 for v in relevance.values()):
        return 0.0

    dcg = sum(
        relevance.get(candidate_id, 0.0) / math.log2(rank + 2)
        for rank, candidate_id in enumerate(ranked_ids[:k])
    )

    ideal_order = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum(rel / math.log2(rank + 2) for rank, rel in enumerate(ideal_order))
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def precision_at_k(ranked_ids: Sequence, relevant_ids: set, k: int) -> float:
    """상위 k개 추천 중 정답(추천해도 무리가 없는 후보)의 비율 — "추천 k개 중 쓸 만한 게 몇 개인가".

    분모는 항상 k다. 추천을 k개보다 적게 내놓은 방법이 유리해지지 않게, 비어 있는 자리는
    틀린 것으로 센다.
    """
    if k <= 0:
        return 0.0
    return len(set(ranked_ids[:k]) & relevant_ids) / k


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """이항 비율(적중률)의 95% 신뢰구간 — Wilson score interval.

    표본이 작거나(실제 사용자 11명) 비율이 0·1에 가까울 때도 구간이 [0, 1] 밖으로 나가지 않아
    정규근사(p ± 1.96·√(p(1-p)/n))보다 이런 평가에 맞다. 두 방법의 구간이 크게 겹치면 그
    차이는 이 표본 크기로는 주장하기 어렵다는 뜻이다.
    """
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, center - half_width), min(1.0, center + half_width))
