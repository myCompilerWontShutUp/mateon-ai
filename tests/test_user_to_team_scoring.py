from app.features.user_to_team.scoring import (
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


def test_label_for_uses_matched_roles_when_available() -> None:
    label = label_for(
        {"role_match": 1.0, "deficit_fit": 0.0},
        matched_roles=["BE", "FE"],
    )
    assert label == "BE, FE 역할을 모집하고 있어요"


def test_label_for_uses_matched_skills_when_available() -> None:
    label = label_for(
        {"role_match": 0.0, "deficit_fit": 1.0},
        matched_skills=["Spring Boot", "PostgreSQL"],
    )
    assert label == "Spring Boot, PostgreSQL 스킬이 필요한 팀이에요"


def test_label_for_uses_activity_style_text() -> None:
    label = label_for(
        {"activity_style_match": 1.0, "role_match": 0.0},
        activity_style="주 2회 오프라인",
    )
    assert label == "'주 2회 오프라인' 방식으로 활동해요"


def test_label_for_beginner_fit_needs_beginner_friendly_flag() -> None:
    label = label_for({"beginner_fit": 1.0, "role_match": 0.0}, beginner_friendly=True)
    assert label == "초보자도 편하게 참여할 수 있는 팀이에요"


def test_label_for_falls_back_when_top_score_is_zero() -> None:
    label = label_for({"role_match": 0.0, "deficit_fit": 0.0})
    assert label == "의미적으로 관심사가 잘 맞아요"


def test_beginner_unfriendly_team_cannot_beat_beginner_friendly_at_half_similarity() -> None:
    # beginner_fit 가중치가 너무 작으면, 유사도(가중치 최대)만으로 "초보자 비친화" 미스매치를
    # 항상 뒤집을 수 있어 초보자에게 초보자 비친화 팀이 1순위로 뜨는 회귀가 생긴다(2026-07-15
    # 실제로 재현됨). 다른 모든 조건이 만점이어도, 초보자 친화 팀은 상대 유사도가 절반만
    # 되어도 최소 동점 이상이어야 한다.
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
