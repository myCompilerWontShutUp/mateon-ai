from app.features.team_to_user.scoring import (
    WEIGHTS,
    deficit_fit_score,
    label_for,
    role_match_score,
)
from app.schemas.recommendation import RecommendationItem, RecommendationRequest, RecommendationResponse
from app.scoring.engine import CandidateInput, rank
from app.scoring.rules import activity_style_match_score, beginner_fit_score, matched_items
from app.scoring.similarity import cosine_similarity

TOP_N = 10


def recommend_users(request: RecommendationRequest) -> RecommendationResponse:
    recruiting_roles = request.query_metadata.get("recruiting_roles", [])
    required_skills = request.query_metadata.get("required_skills", [])
    team_activity_style = request.query_metadata.get("activity_style")
    team_beginner_friendly = request.query_metadata.get("beginner_friendly")

    candidates = []
    label_context = {}
    for candidate in request.candidates:
        similarity = cosine_similarity(request.query_embedding_vector, candidate.embedding_vector)
        candidate_style = candidate.metadata.get("activity_style")
        metadata_scores = {
            "role_match": role_match_score(
                recruiting_roles, candidate.metadata.get("desired_roles", [])
            ),
            "deficit_fit": deficit_fit_score(
                required_skills, candidate.metadata.get("skills", [])
            ),
            "activity_style_match": activity_style_match_score(team_activity_style, candidate_style),
            "beginner_fit": beginner_fit_score(
                candidate.metadata.get("experience_level"), team_beginner_friendly
            ),
        }
        candidates.append(
            CandidateInput(
                candidate_id=candidate.candidate_id,
                raw_similarity=similarity,
                metadata_scores=metadata_scores,
            )
        )
        label_context[candidate.candidate_id] = {
            "matched_roles": matched_items(recruiting_roles, candidate.metadata.get("desired_roles", [])),
            "matched_skills": matched_items(required_skills, candidate.metadata.get("skills", [])),
            "activity_style": candidate_style,
            "beginner_friendly": team_beginner_friendly,
        }

    ranked = rank(candidates, WEIGHTS)[:TOP_N]

    items = [
        RecommendationItem(
            candidate_id=c.candidate_id,
            score=c.total_score,
            label=label_for(c.metadata_scores, **label_context[c.candidate_id]),
        )
        for c in ranked
    ]
    return RecommendationResponse(recommendations=items)
