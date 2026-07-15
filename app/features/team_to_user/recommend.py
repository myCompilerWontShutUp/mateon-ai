from app.features.team_to_user.scoring import (
    WEIGHTS,
    activity_goal_match_score,
    deficit_fit_score,
    label_for,
    portfolio_role_fit_score,
    role_match_score,
)
from app.schemas.recommendation import RecommendationItem, RecommendationRequest, RecommendationResponse
from app.scoring.engine import CandidateInput, rank
from app.scoring.similarity import cosine_similarity

TOP_N = 10


def recommend_users(request: RecommendationRequest) -> RecommendationResponse:
    recruiting_roles = request.query_metadata.get("recruiting_roles", [])
    required_skills = request.query_metadata.get("required_skills", [])
    team_activity_goal = request.query_metadata.get("activity_goal")

    candidates = []
    for candidate in request.candidates:
        similarity = cosine_similarity(request.query_embedding_vector, candidate.embedding_vector)
        metadata_scores = {
            "role_match": role_match_score(
                recruiting_roles, candidate.metadata.get("desired_roles", [])
            ),
            "deficit_fit": deficit_fit_score(
                required_skills, candidate.metadata.get("skills", [])
            ),
            "portfolio_role_fit": portfolio_role_fit_score(
                candidate.metadata.get("experience_level")
            ),
            "activity_goal_match": activity_goal_match_score(
                team_activity_goal, candidate.metadata.get("activity_goal")
            ),
        }
        candidates.append(
            CandidateInput(
                candidate_id=candidate.candidate_id,
                raw_similarity=similarity,
                metadata_scores=metadata_scores,
            )
        )

    ranked = rank(candidates, WEIGHTS)[:TOP_N]

    items = [
        RecommendationItem(
            candidate_id=c.candidate_id, score=c.total_score, label=label_for(c.metadata_scores)
        )
        for c in ranked
    ]
    return RecommendationResponse(recommendations=items)
