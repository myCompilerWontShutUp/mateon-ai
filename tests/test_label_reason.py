"""추천 라벨은 "실제로 맞았다"는 점수만 근거로 삼는다(2026-11-05 수정).

수정 전에는 초보자가 아닌 사용자에게 beginner_fit이 항상 1.0("해당 없음")이라, 역할이 안 맞는 팀이면
초보자를 받지 않는 팀에도 "초보자도 편하게 참여할 수 있어요"가 붙었다(평가 데이터 Top10의 3%,
유저 50명 중 11명). 같은 이유로 CF 라벨은 비초보자에게 사실상 나오지 않았다.
"""

import pytest

from app.features.team_to_user.recommend import recommend_users
from app.features.team_to_user.scoring import label_for as team_to_user_label_for
from app.features.user_to_team.recommend import recommend_teams
from app.features.user_to_team.scoring import label_for as user_to_team_label_for
from app.schemas.recommendation import CandidateEmbedding, RecommendationRequest
from app.scoring.label_reason import pick_label_reason

_DIM = 1536


def _scores(**overrides) -> dict:
    base = {
        "role_match": 0.0,
        "deficit_fit": 0.0,
        "activity_style_match": 0.5,
        "beginner_fit": 1.0,
        "cf_affinity": 0.0,
    }
    base.update(overrides)
    return base


def test_non_beginner_never_gets_the_beginner_label_from_a_team_that_refuses_beginners() -> None:
    label = user_to_team_label_for(_scores(), beginner_friendly=False, seeker_is_beginner=False)
    assert "초보자" not in label
    assert label == "의미적으로 관심사가 잘 맞아요"


def test_non_beginner_does_not_get_beginner_label_even_from_a_friendly_team() -> None:
    label = user_to_team_label_for(_scores(), beginner_friendly=True, seeker_is_beginner=False)
    assert "초보자" not in label


def test_beginner_meets_beginner_friendly_team() -> None:
    assert (
        user_to_team_label_for(_scores(), beginner_friendly=True, seeker_is_beginner=True)
        == "초보자도 편하게 참여할 수 있는 팀이에요"
    )
    assert (
        team_to_user_label_for(_scores(), beginner_friendly=True, seeker_is_beginner=True)
        == "초보자도 편하게 합류할 수 있어요"
    )


def test_unknown_experience_does_not_get_the_beginner_label() -> None:
    """경험 수준을 모르면(None) beginner_fit 1.0은 "해당 없음"이다 — beginner_fit_score도 모르는 경우를
    비초보자로 취급하므로 라벨도 같은 기준을 쓴다."""
    for label_for in (user_to_team_label_for, team_to_user_label_for):
        label = label_for(_scores(), beginner_friendly=True, seeker_is_beginner=None)
        assert "초보자" not in label


def test_cf_label_is_reachable_for_non_beginners() -> None:
    label = user_to_team_label_for(
        _scores(role_match=0.5, cf_affinity=0.8), matched_roles=["BE"], seeker_is_beginner=False
    )
    # 희망 역할 둘 중 하나만 맞은 것(0.5)보다 CF 0.8이 강한 근거다.
    assert label == "비슷한 공모전을 찾아본 사람들이 함께 관심을 보인 팀이에요"


def test_unknown_activity_style_is_not_a_reason() -> None:
    # 0.5는 한쪽 활동 방식을 모른다는 중립값 — "'온라인' 방식으로 활동해요"를 붙이면 안 된다.
    label = user_to_team_label_for(_scores(), activity_style="ONLINE", seeker_is_beginner=False)
    assert "방식으로 활동해요" not in label
    assert (
        user_to_team_label_for(_scores(activity_style_match=1.0), activity_style="ONLINE", seeker_is_beginner=False)
        == "'온라인' 방식으로 활동해요"
    )


def test_labels_show_korean_role_and_style_labels_not_codes() -> None:
    """라벨에 코드 값("COOK_WESTERN", "HYBRID")이 그대로 노출되지 않는다."""
    assert (
        user_to_team_label_for({"role_match": 1.0, "deficit_fit": 0.0}, matched_roles=["COOK_WESTERN"])
        == "양식 요리 역할을 모집하고 있어요"
    )
    assert (
        team_to_user_label_for({"role_match": 1.0, "deficit_fit": 0.0}, matched_roles=["VIDEO_EDITING"])
        == "영상 편집 역할에 지원 가능해요"
    )
    assert (
        user_to_team_label_for({"activity_style_match": 1.0, "role_match": 0.0}, activity_style="HYBRID")
        == "'온·오프라인 병행' 방식으로 활동해요"
    )


def test_ties_prefer_specific_matches() -> None:
    assert pick_label_reason(_scores(role_match=1.0, cf_affinity=1.0), beginner_relevant=False) == "role_match"
    assert pick_label_reason(_scores(deficit_fit=1.0, cf_affinity=1.0), beginner_relevant=False) == "deficit_fit"
    assert (
        pick_label_reason(_scores(activity_style_match=1.0, cf_affinity=1.0), beginner_relevant=False)
        == "cf_affinity"
    )
    assert pick_label_reason(_scores(), beginner_relevant=False) is None


async def test_recommendations_for_non_beginner_carry_no_misleading_beginner_label() -> None:
    """재현했던 상황 그대로: 중급 사용자, 역할이 안 맞는 팀들, 그중 하나는 초보자를 받지 않는다."""
    vector = [1.0] + [0.0] * (_DIM - 1)
    request = RecommendationRequest(
        query_embedding_vector=vector,
        query_metadata={"desired_roles": ["COOK_WESTERN"], "skills": [], "experience_level": "intermediate"},
        candidates=[
            CandidateEmbedding(
                candidate_id=1,
                embedding_vector=vector,
                metadata={"recruiting_roles": ["BE"], "beginner_friendly": False},
            ),
            CandidateEmbedding(
                candidate_id=2,
                embedding_vector=vector,
                metadata={"recruiting_roles": ["PM"], "beginner_friendly": None},
            ),
        ],
    )

    response = await recommend_teams(request)

    assert all("초보자" not in item.label for item in response.recommendations)


def _vector() -> list[float]:
    return [1.0] + [0.0] * (_DIM - 1)


@pytest.mark.parametrize(
    ("experience_level", "expects_beginner_label"),
    [("beginner", True), ("intermediate", False), (None, False)],
)
async def test_recommend_teams_passes_seeker_experience_to_the_label(
    experience_level: str | None, expects_beginner_label: bool
) -> None:
    """라벨 문맥(사용자 경험 수준 × 팀의 초보자 환영 여부)이 recommend_teams까지 실제로 이어지는지 본다."""
    request = RecommendationRequest(
        query_embedding_vector=_vector(),
        query_metadata={"desired_roles": ["COOK_WESTERN"], "experience_level": experience_level},
        candidates=[
            CandidateEmbedding(
                candidate_id=1,
                embedding_vector=_vector(),
                metadata={"recruiting_roles": ["BE"], "beginner_friendly": True},
            )
        ],
    )

    [item] = (await recommend_teams(request)).recommendations

    assert ("초보자" in item.label) is expects_beginner_label


@pytest.mark.parametrize(
    ("experience_level", "expects_beginner_label"),
    [("beginner", True), ("intermediate", False), (None, False)],
)
async def test_recommend_users_passes_candidate_experience_to_the_label(
    experience_level: str | None, expects_beginner_label: bool
) -> None:
    request = RecommendationRequest(
        query_embedding_vector=_vector(),
        query_metadata={"recruiting_roles": ["BE"], "beginner_friendly": True},
        candidates=[
            CandidateEmbedding(
                candidate_id=1,
                embedding_vector=_vector(),
                metadata={"desired_roles": ["COOK_WESTERN"], "experience_level": experience_level},
            )
        ],
    )

    [item] = (await recommend_users(request)).recommendations

    assert ("초보자" in item.label) is expects_beginner_label
