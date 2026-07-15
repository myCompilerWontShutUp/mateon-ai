from app.features.user_to_team.scoring import (
    deficit_fit_score,
    label_for,
    role_match_score,
)
from app.scoring.rules import activity_style_match_score, beginner_fit_score


def test_role_match_full_overlap() -> None:
    assert role_match_score(["BE"], ["BE", "FE"]) == 1.0


def test_role_match_no_overlap() -> None:
    assert role_match_score(["BE"], ["FE"]) == 0.0


def test_role_match_empty_inputs() -> None:
    assert role_match_score([], ["BE"]) == 0.0
    assert role_match_score(["BE"], []) == 0.0


def test_deficit_fit_partial_overlap() -> None:
    score = deficit_fit_score(["Spring Boot"], ["Spring Boot", "PostgreSQL"])
    assert score == 0.5


def test_activity_style_match_exact() -> None:
    assert activity_style_match_score("주 2회 오프라인", "주 2회 오프라인") == 1.0


def test_activity_style_match_mismatch() -> None:
    assert activity_style_match_score("주 2회 오프라인", "온라인") == 0.0


def test_activity_style_match_missing_info_is_neutral() -> None:
    assert activity_style_match_score(None, "온라인") == 0.5


def test_beginner_fit_beginner_in_friendly_team() -> None:
    assert beginner_fit_score("beginner", True) == 1.0


def test_beginner_fit_beginner_in_unfriendly_team() -> None:
    assert beginner_fit_score("beginner", False) == 0.0


def test_beginner_fit_non_beginner_is_unaffected() -> None:
    assert beginner_fit_score("advanced", False) == 1.0


def test_label_for_picks_highest_component() -> None:
    label = label_for({"role_match": 0.2, "deficit_fit": 0.9, "beginner_fit": 0.1})
    assert label == "팀이 필요한 스킬을 갖췄어요"
