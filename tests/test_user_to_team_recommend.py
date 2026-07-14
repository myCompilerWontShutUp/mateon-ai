from app.features.user_to_team.recommend import recommend_teams
from app.schemas.recommendation import CandidateEmbedding, RecommendationRequest


def test_recommend_teams_ranks_better_role_match_higher() -> None:
    request = RecommendationRequest(
        query_embedding_vector=[1.0, 0.0],
        query_metadata={
            "desired_roles": ["BE"],
            "skills": ["Spring Boot"],
            "activity_style": "온라인",
            "experience_level": "beginner",
        },
        candidates=[
            CandidateEmbedding(
                candidate_id=1,
                embedding_vector=[1.0, 0.0],
                metadata={
                    "recruiting_roles": ["BE"],
                    "required_skills": ["Spring Boot"],
                    "activity_style": "온라인",
                    "beginner_friendly": True,
                },
            ),
            CandidateEmbedding(
                candidate_id=2,
                embedding_vector=[1.0, 0.0],
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
    assert response.recommendations[0].label != ""


def test_recommend_teams_caps_at_top_n() -> None:
    candidates = [
        CandidateEmbedding(candidate_id=i, embedding_vector=[1.0, 0.0], metadata={})
        for i in range(15)
    ]
    request = RecommendationRequest(
        query_embedding_vector=[1.0, 0.0], query_metadata={}, candidates=candidates
    )

    response = recommend_teams(request)

    assert len(response.recommendations) == 10
