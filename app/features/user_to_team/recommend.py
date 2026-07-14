from app.features.user_to_team.scoring import (
    WEIGHTS,
    activity_style_match_score,
    beginner_fit_score,
    deficit_fit_score,
    label_for,
    role_match_score,
)
from app.schemas.recommendation import RecommendationItem, RecommendationRequest, RecommendationResponse
from app.scoring.engine import CandidateInput, rank
from app.scoring.similarity import cosine_similarity

TOP_N = 10


def recommend_teams(request: RecommendationRequest) -> RecommendationResponse:
    desired_roles = request.query_metadata.get("desired_roles", [])
    skills = request.query_metadata.get("skills", [])
    activity_style = request.query_metadata.get("activity_style")
    experience_level = request.query_metadata.get("experience_level")

    candidates = []
    for candidate in request.candidates:
        similarity = cosine_similarity(request.query_embedding_vector, candidate.embedding_vector)
        metadata_scores = {
            "role_match": role_match_score(
                desired_roles, candidate.metadata.get("recruiting_roles", [])
            ),
            "deficit_fit": deficit_fit_score(
                skills, candidate.metadata.get("required_skills", [])
            ),
            "activity_style_match": activity_style_match_score(
                activity_style, candidate.metadata.get("activity_style")
            ),
            "beginner_fit": beginner_fit_score(
                experience_level, candidate.metadata.get("beginner_friendly")
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
