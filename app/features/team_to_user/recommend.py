import asyncio

from app.features.team_to_user.scoring import (
    PENALTY_RULES,
    WEIGHTS,
    deficit_fit_score,
    label_for,
    role_match_score,
)
from app.schemas.recommendation import RecommendationItem, RecommendationRequest, RecommendationResponse
from app.scoring.cluster import team_cluster_key
from app.scoring.cluster_weight_store import read_cluster_lifts
from app.scoring.cluster_weights import adjust_weights
from app.scoring.engine import CandidateInput, rank
from app.scoring.rules import (
    activity_style_match_score,
    activity_time_match_score,
    beginner_fit_score,
    matched_items,
)
from app.scoring.similarity import cosine_similarity

TOP_N = 10


async def recommend_users(request: RecommendationRequest) -> RecommendationResponse:
    recruiting_roles = request.query_metadata.get("recruiting_roles", [])
    required_skills = request.query_metadata.get("required_skills", [])
    team_activity_style = request.query_metadata.get("activity_style")
    team_beginner_friendly = request.query_metadata.get("beginner_friendly")
    team_activity_time = request.query_metadata.get("activity_time")
    team_contest_field = request.query_metadata.get("contest_field")

    # 1번 항목 — user_to_team/recommend.py와 동일한 패턴(주석 참고). 팀 클러스터 키는
    # recruiting_roles × contest_field(사용자 쪽 desired_roles × experience_level과 대칭,
    # CLAUDE.md 참고).
    cluster_key = team_cluster_key(recruiting_roles, team_contest_field)
    cluster_lifts = await asyncio.to_thread(read_cluster_lifts)
    weights = adjust_weights(WEIGHTS, cluster_lifts.get(cluster_key, {}))

    candidates = []
    label_context = {}
    # 선택 필드(activity_time) 점수는 metadata_scores와 분리해서 들고 있는다 — WEIGHTS에 없는
    # 키가 섞이면 label_for()의 "가장 점수가 높은 컴포넌트" 판단을 흐릴 수 있다.
    optional_scores = {}
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
        optional_scores[candidate.candidate_id] = {
            "activity_time_match": activity_time_match_score(
                team_activity_time, candidate.metadata.get("activity_time")
            ),
        }

    ranked = rank(candidates, weights, PENALTY_RULES)[:TOP_N]

    items = [
        RecommendationItem(
            candidate_id=c.candidate_id,
            score=c.total_score,
            label=label_for(c.metadata_scores, **label_context[c.candidate_id]),
            component_scores={
                "similarity": c.similarity,
                **c.metadata_scores,
                **optional_scores[c.candidate_id],
            },
        )
        for c in ranked
    ]
    return RecommendationResponse(recommendations=items)
