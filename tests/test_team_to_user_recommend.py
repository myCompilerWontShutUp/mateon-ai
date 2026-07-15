from app.features.team_to_user.recommend import recommend_users
from app.schemas.recommendation import CandidateEmbedding, RecommendationRequest

DUMMY_VECTOR = [1.0] + [0.0] * 1535


def test_recommend_users_ranks_better_role_match_higher() -> None:
    request = RecommendationRequest(
        query_embedding_vector=DUMMY_VECTOR,
        query_metadata={
            "recruiting_roles": ["BE"],
            "required_skills": ["Spring Boot"],
            "activity_goal": "공모전 수상",
        },
        candidates=[
            CandidateEmbedding(
                candidate_id=101,
                embedding_vector=DUMMY_VECTOR,
                metadata={
                    "desired_roles": ["BE"],
                    "skills": ["Spring Boot"],
                    "experience_level": "advanced",
                    "activity_goal": "공모전 수상",
                },
            ),
            CandidateEmbedding(
                candidate_id=102,
                embedding_vector=DUMMY_VECTOR,
                metadata={
                    "desired_roles": ["FE"],
                    "skills": ["React"],
                    "experience_level": "beginner",
                    "activity_goal": "가볍게 참여",
                },
            ),
        ],
    )

    response = recommend_users(request)

    assert [item.candidate_id for item in response.recommendations] == [101, 102]
    assert response.recommendations[0].score > response.recommendations[1].score


def test_recommend_users_caps_at_top_n() -> None:
    candidates = [
        CandidateEmbedding(candidate_id=i, embedding_vector=DUMMY_VECTOR, metadata={})
        for i in range(15)
    ]
    request = RecommendationRequest(
        query_embedding_vector=DUMMY_VECTOR, query_metadata={}, candidates=candidates
    )

    response = recommend_users(request)

    assert len(response.recommendations) == 10
