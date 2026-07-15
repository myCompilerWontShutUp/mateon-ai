from dataclasses import dataclass, field
from typing import TypeVar

CandidateId = TypeVar("CandidateId")

_SIMILARITY_KEY = "similarity"


@dataclass(frozen=True)
class CandidateInput:
    candidate_id: CandidateId
    raw_similarity: float
    metadata_scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateScore:
    candidate_id: CandidateId
    similarity: float
    metadata_scores: dict[str, float]
    total_score: float


def normalize_similarities(raw_similarities: dict[CandidateId, float]) -> dict[CandidateId, float]:
    if not raw_similarities:
        return {}

    values = raw_similarities.values()
    lo, hi = min(values), max(values)
    if hi == lo:
        return dict.fromkeys(raw_similarities, 1.0)

    return {
        candidate_id: (value - lo) / (hi - lo) for candidate_id, value in raw_similarities.items()
    }


def combine_score(
    similarity: float,
    metadata_scores: dict[str, float],
    weights: dict[str, float],
    penalty_rules: dict[str, tuple[float, float]] | None = None,
) -> float:
    scores = {_SIMILARITY_KEY: similarity, **metadata_scores}
    missing = weights.keys() - scores.keys()
    if missing:
        raise ValueError(f"no score provided for weighted component(s): {sorted(missing)}")

    total = sum(weights[name] * scores[name] for name in weights)

    # 가중 합만으로는 후보군이 적을 때 유사도의 정규화 스윙(min-max라 후보가 2~3개면 사소한
    # 원시 유사도 차이도 0~1로 최대치까지 벌어진다)이 명시적 배제 신호(예: 초보자 비친화)를
    # 항상 뒤집을 수 있다 — 실제로 초보자 유저에게 "초보자는 정중히 지양합니다"라고 쓴 팀이
    # 1순위로 뜬 사례가 있었다(2026-07-15). 특정 구성요소가 최악값(예: beginner_fit == 0.0)일
    # 때는 가중치를 더 올리는 대신 최종 점수에 강한 배율(penalty_rules)을 곱해 순위를 확실히
    # 끌어내린다 — 완전한 하드 필터(후보 제외)는 아니지만, 어지간한 유사도 우위로는 못 뒤집을
    # 만큼 강하게 만든다.
    for component, (trigger_value, multiplier) in (penalty_rules or {}).items():
        if scores.get(component) == trigger_value:
            total *= multiplier

    return total


def rank(
    candidates: list[CandidateInput],
    weights: dict[str, float],
    penalty_rules: dict[str, tuple[float, float]] | None = None,
) -> list[CandidateScore]:
    normalized = normalize_similarities(
        {candidate.candidate_id: candidate.raw_similarity for candidate in candidates}
    )

    scored = [
        CandidateScore(
            candidate_id=candidate.candidate_id,
            similarity=normalized[candidate.candidate_id],
            metadata_scores=candidate.metadata_scores,
            total_score=combine_score(
                normalized[candidate.candidate_id],
                candidate.metadata_scores,
                weights,
                penalty_rules,
            ),
        )
        for candidate in candidates
    ]

    # 메타데이터 점수 상당수가 0/0.5/1 같은 이산값이라 total_score가 동점으로 묶이기 쉽다.
    # 동점일 때 입력 순서에 맡기지 않도록, 가중치가 높은 구성요소부터 순서대로 비교해
    # 결정적인 순위를 만든다.
    tie_break_order = sorted(weights, key=lambda name: weights[name], reverse=True)

    def sort_key(candidate_score: CandidateScore) -> tuple[float, ...]:
        component_scores = {_SIMILARITY_KEY: candidate_score.similarity, **candidate_score.metadata_scores}
        return (
            candidate_score.total_score,
            *(component_scores[name] for name in tie_break_order),
        )

    return sorted(scored, key=sort_key, reverse=True)
