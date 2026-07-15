from app.features.team_to_user.scoring import (
    WEIGHTS,
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


def test_label_for_uses_matched_roles_when_available() -> None:
    label = label_for({"role_match": 1.0, "deficit_fit": 0.0}, matched_roles=["BE"])
    assert label == "BE 역할에 지원 가능해요"


def test_label_for_uses_matched_skills_when_available() -> None:
    label = label_for(
        {"role_match": 0.0, "deficit_fit": 1.0}, matched_skills=["Spring Boot", "Kafka"]
    )
    assert label == "Spring Boot, Kafka 스킬을 갖췄어요"


def test_label_for_falls_back_when_top_score_is_zero() -> None:
    label = label_for({"role_match": 0.0, "deficit_fit": 0.0})
    assert label == "의미적으로 결핍과 잘 맞아요"


def test_beginner_unfriendly_team_cannot_beat_beginner_friendly_at_half_similarity() -> None:
    from app.scoring.engine import combine_score

    anti_beginner_full_match = combine_score(
        similarity=1.0,
        metadata_scores={
            "role_match": 1.0, "deficit_fit": 1.0, "activity_style_match": 1.0, "beginner_fit": 0.0,
        },
        weights=WEIGHTS,
    )
    beginner_friendly_half_similarity = combine_score(
        similarity=0.5,
        metadata_scores={
            "role_match": 1.0, "deficit_fit": 1.0, "activity_style_match": 1.0, "beginner_fit": 1.0,
        },
        weights=WEIGHTS,
    )
    assert beginner_friendly_half_similarity >= anti_beginner_full_match
