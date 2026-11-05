import pytest

from app.scoring.behavior_blend import ALPHA_FLOOR, blend_query_vector, intent_weight


def test_no_history_keeps_intent_fully() -> None:
    assert intent_weight(0) == 1.0


def test_alpha_decreases_as_history_grows() -> None:
    assert intent_weight(1) > intent_weight(3) > intent_weight(5)


def test_alpha_never_falls_below_floor() -> None:
    """명시적으로 말한 의도가 과거 행동에 완전히 묻히면 안 된다."""
    assert intent_weight(1000) == ALPHA_FLOOR


def test_blend_without_behavior_vector_returns_intent_unchanged() -> None:
    intent = [1.0, 0.0, 0.0]
    assert blend_query_vector(intent, None, interaction_count=10) == intent


def test_blend_with_zero_interactions_returns_intent_unchanged() -> None:
    """BE가 벡터는 보냈지만 이력이 0건이면 행동 벡터를 반영하지 않는다."""
    intent = [1.0, 0.0, 0.0]
    behavior = [0.0, 1.0, 0.0]
    assert blend_query_vector(intent, behavior, interaction_count=0) == intent


def test_blend_moves_vector_toward_behavior() -> None:
    intent = [1.0, 0.0]
    behavior = [0.0, 1.0]

    blended = blend_query_vector(intent, behavior, interaction_count=5)

    alpha = intent_weight(5)
    assert blended == pytest.approx([alpha, 1.0 - alpha])
    # 이력이 많을수록 행동 쪽으로 더 이동한다.
    assert blended[1] > blend_query_vector(intent, behavior, interaction_count=1)[1]


def test_blend_rejects_dimension_mismatch() -> None:
    with pytest.raises(ValueError):
        blend_query_vector([1.0, 0.0], [0.0, 1.0, 0.0], interaction_count=5)
