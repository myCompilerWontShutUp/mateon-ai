from app.features.team_to_user.scoring import (
    activity_goal_match_score,
    deficit_fit_score,
    label_for,
    portfolio_role_fit_score,
    role_match_score,
)


def test_role_match_full_overlap() -> None:
    assert role_match_score(["BE"], ["BE", "FE"]) == 1.0


def test_role_match_no_overlap() -> None:
    assert role_match_score(["BE"], ["FE"]) == 0.0


def test_deficit_fit_partial_overlap() -> None:
    assert deficit_fit_score(["Spring Boot", "PostgreSQL"], ["Spring Boot"]) == 0.5


def test_portfolio_role_fit_advanced_is_highest() -> None:
    assert portfolio_role_fit_score("advanced") == 1.0
    assert portfolio_role_fit_score("beginner") == 0.3
    assert portfolio_role_fit_score(None) == 0.5


def test_activity_goal_match_exact() -> None:
    assert activity_goal_match_score("공모전 수상", "공모전 수상") == 1.0


def test_activity_goal_match_missing_is_neutral() -> None:
    assert activity_goal_match_score(None, "공모전 수상") == 0.5


def test_label_for_picks_highest_component() -> None:
    label = label_for({"role_match": 0.9, "deficit_fit": 0.1, "portfolio_role_fit": 0.2})
    assert label == "팀의 결핍 역할과 일치해요"
