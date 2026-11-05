"""행동 임베딩 블렌딩이 추천 경로에 제대로 배선됐는지 검증한다.

핵심은 두 가지다 — (1) BE가 새 필드를 안 보내는 동안 기존과 완전히 동일하게 동작할 것
(하위 호환), (2) 이력을 보내면 실제로 그 방향으로 순위가 움직일 것.
"""

from app.features.user_to_team.recommend import recommend_teams
from app.schemas.recommendation import CandidateEmbedding, RecommendationRequest

_DIM = 1536


def _unit(index: int) -> list[float]:
    vector = [0.0] * _DIM
    vector[index] = 1.0
    return vector


INTENT = _unit(0)
BEHAVIOR = _unit(1)


def _mixed(intent_part: float, behavior_part: float) -> list[float]:
    """intent 축과 행동 축에 동시에 걸쳐 있는 팀 — 현실의 후보는 대부분 이 모양이다."""
    vector = [0.0] * _DIM
    vector[0] = intent_part
    vector[1] = behavior_part
    return vector

# 메타데이터 룰 점수가 모든 후보에서 동일하도록 맞춘다 — 순위 차이가 오직 임베딩 유사도에서만
# 나오게 해서 블렌딩 효과를 격리한다.
_SHARED_METADATA = {
    "recruiting_roles": ["BE"],
    "required_skills": ["Spring Boot"],
    "activity_style": "온라인",
    "beginner_friendly": True,
}


def _request(**kwargs) -> RecommendationRequest:
    return RecommendationRequest(
        query_embedding_vector=INTENT,
        query_metadata={
            "desired_roles": ["BE"],
            "skills": ["Spring Boot"],
            "activity_style": "온라인",
            "experience_level": "beginner",
        },
        candidates=[
            # 1번: intent 축에만 정렬된 팀.
            CandidateEmbedding(candidate_id=1, embedding_vector=INTENT, metadata=_SHARED_METADATA),
            # 2번: 행동 축 위주지만 intent와도 약간 겹치는 팀 — intent만 보면 1번에 밀린다.
            CandidateEmbedding(
                candidate_id=2, embedding_vector=_mixed(0.3, 0.954), metadata=_SHARED_METADATA
            ),
        ],
        **kwargs,
    )


async def test_without_behavior_fields_intent_aligned_team_wins() -> None:
    """BE 미연동 상태(필드 없음) — 기존 동작 그대로."""
    response = await recommend_teams(_request())

    assert [item.candidate_id for item in response.recommendations] == [1, 2]


async def test_behavior_history_lifts_behavior_aligned_team() -> None:
    """행동 이력이 쌓이면 intent만으로는 밀렸던 팀이 1위로 올라온다."""
    response = await recommend_teams(
        _request(behavior_embedding_vector=BEHAVIOR, interaction_count=20)
    )

    assert [item.candidate_id for item in response.recommendations] == [2, 1]


async def test_behavior_can_match_but_never_outweigh_stated_intent() -> None:
    """α 바닥값(0.5)의 안전 속성 — 이력이 아무리 많아도 행동이 명시적 의도를 덮어쓰지 못한다.

    intent에만 정렬된 팀과 행동에만 정렬된 팀을 두면, 최대치에서도 유사도가 동점에 그친다.
    사용자가 이번 검색에서 직접 말한 조건이 과거 이력에 묻히면 안 되기 때문이다.
    """
    request = RecommendationRequest(
        query_embedding_vector=INTENT,
        query_metadata={"desired_roles": ["BE"], "experience_level": "beginner"},
        candidates=[
            CandidateEmbedding(candidate_id=1, embedding_vector=INTENT, metadata=_SHARED_METADATA),
            CandidateEmbedding(candidate_id=2, embedding_vector=BEHAVIOR, metadata=_SHARED_METADATA),
        ],
        behavior_embedding_vector=BEHAVIOR,
        interaction_count=10_000,
    )

    response = await recommend_teams(request)

    scores = {item.candidate_id: item.component_scores["similarity"] for item in response.recommendations}
    assert scores[1] == scores[2]


async def test_zero_interaction_count_is_identical_to_omitting_the_field() -> None:
    """벡터를 보내도 이력이 0건이면 반영하지 않는다 — 하위 호환의 핵심 경계값."""
    baseline = await recommend_teams(_request())
    with_zero = await recommend_teams(
        _request(behavior_embedding_vector=BEHAVIOR, interaction_count=0)
    )

    assert [i.candidate_id for i in with_zero.recommendations] == [
        i.candidate_id for i in baseline.recommendations
    ]
    assert [i.score for i in with_zero.recommendations] == [
        i.score for i in baseline.recommendations
    ]
