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
    similarity: float, metadata_scores: dict[str, float], weights: dict[str, float]
) -> float:
    scores = {_SIMILARITY_KEY: similarity, **metadata_scores}
    missing = weights.keys() - scores.keys()
    if missing:
        raise ValueError(f"no score provided for weighted component(s): {sorted(missing)}")

    return sum(weights[name] * scores[name] for name in weights)


def rank(candidates: list[CandidateInput], weights: dict[str, float]) -> list[CandidateScore]:
    normalized = normalize_similarities(
        {candidate.candidate_id: candidate.raw_similarity for candidate in candidates}
    )

    scored = [
        CandidateScore(
            candidate_id=candidate.candidate_id,
            similarity=normalized[candidate.candidate_id],
            metadata_scores=candidate.metadata_scores,
            total_score=combine_score(
                normalized[candidate.candidate_id], candidate.metadata_scores, weights
            ),
        )
        for candidate in candidates
    ]

    return sorted(scored, key=lambda candidate_score: candidate_score.total_score, reverse=True)
