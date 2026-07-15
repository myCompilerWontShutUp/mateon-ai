from app.features.team_to_user.scoring import (
    deficit_fit_score,
    label_for,
    role_match_score,
)
from app.scoring.rules import activity_style_match_score, beginner_fit_score


def test_role_match_full_overlap() -> None:
    assert role_match_score(["BE"], ["BE", "FE"]) == 1.0


def test_role_match_no_overlap() -> None:
    assert role_match_score(["BE"], ["FE"]) == 0.0


def test_deficit_fit_partial_overlap() -> None:
    assert deficit_fit_score(["Spring Boot", "PostgreSQL"], ["Spring Boot"]) == 0.5


def test_activity_style_match_exact() -> None:
    assert activity_style_match_score("오프라인 모임", "오프라인 모임") == 1.0


def test_activity_style_match_missing_is_neutral() -> None:
    assert activity_style_match_score(None, "오프라인 모임") == 0.5


def test_beginner_fit_matches_team_openness() -> None:
    assert beginner_fit_score("beginner", True) == 1.0
    assert beginner_fit_score("beginner", False) == 0.0
    assert beginner_fit_score("advanced", False) == 1.0


def test_label_for_picks_highest_component() -> None:
    label = label_for({"role_match": 0.9, "deficit_fit": 0.1, "activity_style_match": 0.2})
    assert label == "팀의 결핍 역할과 일치해요"
