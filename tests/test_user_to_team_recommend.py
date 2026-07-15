from app.features.user_to_team.recommend import recommend_teams
from app.schemas.recommendation import CandidateEmbedding, RecommendationRequest

DUMMY_VECTOR = [1.0] + [0.0] * 1535


def test_recommend_teams_ranks_better_role_match_higher() -> None:
    request = RecommendationRequest(
        query_embedding_vector=DUMMY_VECTOR,
        query_metadata={
            "desired_roles": ["BE"],
            "skills": ["Spring Boot"],
            "activity_style": "온라인",
            "experience_level": "beginner",
        },
        candidates=[
            CandidateEmbedding(
                candidate_id=1,
                embedding_vector=DUMMY_VECTOR,
                metadata={
                    "recruiting_roles": ["BE"],
                    "required_skills": ["Spring Boot"],
                    "activity_style": "온라인",
                    "beginner_friendly": True,
                },
            ),
            CandidateEmbedding(
                candidate_id=2,
                embedding_vector=DUMMY_VECTOR,
                metadata={
                    "recruiting_roles": ["FE"],
                    "required_skills": ["React"],
                    "activity_style": "오프라인",
                    "beginner_friendly": False,
                },
            ),
        ],
    )

    response = recommend_teams(request)

    assert [item.candidate_id for item in response.recommendations] == [1, 2]
    assert response.recommendations[0].score > response.recommendations[1].score
    assert response.recommendations[0].label == "BE 역할을 모집하고 있어요"


def test_beginner_unfriendly_team_does_not_win_on_tiny_similarity_edge() -> None:
    # 회귀 재현(2026-07-15): 팀 소개 텍스트가 거의 동일하고 "초보자 지양" 여부만 다르면 원시
    # 유사도 차이가 아주 작다. 후보가 2개뿐이면 min-max 정규화가 이 작은 차이를 1.0 vs 0.0으로
    # 벌려버려서, 그것만으로 beginner_fit 미스매치를 뒤집고 "초보자 지양" 팀이 1위로 나왔다.
    query_vector = [1.0] + [0.0] * 1535
    slightly_more_similar = [0.999, 0.001] + [0.0] * 1534  # 초보자 지양 팀 (근소하게 더 유사)
    slightly_less_similar = [0.998, 0.002] + [0.0] * 1534  # 초보자 친화 팀

    request = RecommendationRequest(
        query_embedding_vector=query_vector,
        query_metadata={
            "desired_roles": ["BE"], "skills": [], "activity_style": None, "experience_level": "beginner",
        },
        candidates=[
            CandidateEmbedding(
                candidate_id=1,  # 초보자 지양 팀, 근소하게 더 유사
                embedding_vector=slightly_more_similar,
                metadata={
                    "recruiting_roles": ["BE"], "required_skills": ["Spring Boot"],
                    "activity_style": None, "beginner_friendly": False,
                },
            ),
            CandidateEmbedding(
                candidate_id=2,  # 초보자 친화 팀
                embedding_vector=slightly_less_similar,
                metadata={
                    "recruiting_roles": ["BE"], "required_skills": ["Spring Boot"],
                    "activity_style": None, "beginner_friendly": True,
                },
            ),
        ],
    )

    response = recommend_teams(request)

    assert response.recommendations[0].candidate_id == 2, (
        f"1위가 초보자 친화 팀(2)이어야 하는데: {response.recommendations}"
    )


def test_recommend_teams_caps_at_top_n() -> None:
    candidates = [
        CandidateEmbedding(candidate_id=i, embedding_vector=DUMMY_VECTOR, metadata={})
        for i in range(15)
    ]
    request = RecommendationRequest(
        query_embedding_vector=DUMMY_VECTOR, query_metadata={}, candidates=candidates
    )

    response = recommend_teams(request)

    assert len(response.recommendations) == 10
