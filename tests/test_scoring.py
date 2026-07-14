import pytest

from app.scoring.engine import CandidateInput, combine_score, normalize_similarities, rank


def test_normalize_similarities_min_max() -> None:
    result = normalize_similarities({"a": 0.5, "b": 0.7, "c": 0.9})
    assert result == pytest.approx({"a": 0.0, "b": 0.5, "c": 1.0})


def test_normalize_similarities_constant_values() -> None:
    result = normalize_similarities({"a": 0.6, "b": 0.6})
    assert result == {"a": 1.0, "b": 1.0}


def test_normalize_similarities_empty() -> None:
    assert normalize_similarities({}) == {}


def test_combine_score_weighted_sum() -> None:
    score = combine_score(
        similarity=0.8,
        metadata_scores={"role_match": 0.5, "deficit_fit": 1.0},
        weights={"similarity": 0.5, "role_match": 0.3, "deficit_fit": 0.2},
    )
    assert score == pytest.approx(0.8 * 0.5 + 0.5 * 0.3 + 1.0 * 0.2)


def test_combine_score_missing_component_raises() -> None:
    with pytest.raises(ValueError, match="beginner_fit"):
        combine_score(similarity=0.5, metadata_scores={}, weights={"beginner_fit": 1.0})


def test_rank_orders_by_total_score_descending() -> None:
    candidates = [
        CandidateInput(candidate_id="low", raw_similarity=0.1, metadata_scores={"role_match": 0.0}),
        CandidateInput(candidate_id="high", raw_similarity=0.9, metadata_scores={"role_match": 1.0}),
        CandidateInput(candidate_id="mid", raw_similarity=0.5, metadata_scores={"role_match": 0.5}),
    ]
    weights = {"similarity": 0.5, "role_match": 0.5}

    ranked = rank(candidates, weights)

    assert [c.candidate_id for c in ranked] == ["high", "mid", "low"]
    assert ranked[0].total_score > ranked[1].total_score > ranked[2].total_score
