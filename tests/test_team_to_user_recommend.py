from app.features.team_to_user.recommend import recommend_users
from app.schemas.recommendation import CandidateEmbedding, RecommendationRequest

DUMMY_VECTOR = [1.0] + [0.0] * 1535


async def test_recommend_users_ranks_better_role_match_higher() -> None:
    request = RecommendationRequest(
        query_embedding_vector=DUMMY_VECTOR,
        query_metadata={
            "recruiting_roles": ["BE"],
            "required_skills": ["Spring Boot"],
            "activity_style": "오프라인 모임",
            "beginner_friendly": False,
        },
        candidates=[
            CandidateEmbedding(
                candidate_id=101,
                embedding_vector=DUMMY_VECTOR,
                metadata={
                    "desired_roles": ["BE"],
                    "skills": ["Spring Boot"],
                    "experience_level": "advanced",
                    "activity_style": "오프라인 모임",
                },
            ),
            CandidateEmbedding(
                candidate_id=102,
                embedding_vector=DUMMY_VECTOR,
                metadata={
                    "desired_roles": ["FE"],
                    "skills": ["React"],
                    "experience_level": "beginner",
                    "activity_style": "온라인",
                },
            ),
        ],
    )

    response = await recommend_users(request)

    assert [item.candidate_id for item in response.recommendations] == [101, 102]
    assert response.recommendations[0].score > response.recommendations[1].score
    assert response.recommendations[0].label == "BE 역할에 지원 가능해요"


async def test_activity_time_is_exposed_but_does_not_affect_score_or_label() -> None:
    def _request(candidate_activity_time: str | None) -> RecommendationRequest:
        return RecommendationRequest(
            query_embedding_vector=DUMMY_VECTOR,
            query_metadata={
                "recruiting_roles": ["BE"],
                "required_skills": ["Spring Boot"],
                "activity_time": "평일 저녁",
            },
            candidates=[
                CandidateEmbedding(
                    candidate_id=101,
                    embedding_vector=DUMMY_VECTOR,
                    metadata={
                        "desired_roles": ["BE"],
                        "skills": ["Spring Boot"],
                        "activity_time": candidate_activity_time,
                    },
                ),
            ],
        )

    matching = (await recommend_users(_request("평일 저녁"))).recommendations[0]
    mismatching = (await recommend_users(_request("주말"))).recommendations[0]

    assert matching.component_scores["activity_time_match"] == 1.0
    assert mismatching.component_scores["activity_time_match"] == 0.0
    assert matching.score == mismatching.score
    assert matching.label == mismatching.label


async def test_recommend_users_caps_at_top_n() -> None:
    candidates = [
        CandidateEmbedding(candidate_id=i, embedding_vector=DUMMY_VECTOR, metadata={})
        for i in range(15)
    ]
    request = RecommendationRequest(
        query_embedding_vector=DUMMY_VECTOR, query_metadata={}, candidates=candidates
    )

    response = await recommend_users(request)

    assert len(response.recommendations) == 10
