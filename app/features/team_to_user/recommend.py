import asyncio

from app.features.team_to_user.scoring import (
    PENALTY_RULES,
    WEIGHTS,
    deficit_fit_score,
    label_for,
    role_match_score,
)
from app.schemas.common import MatchDirection
from app.schemas.recommendation import RecommendationItem, RecommendationRequest, RecommendationResponse
from app.scoring.cluster import lift_key, team_cluster_key
from app.scoring.cluster_weight_store import read_cluster_lifts
from app.scoring.cluster_weights import adjust_weights
from app.scoring.cooccurrence import as_event_id, as_event_ids, cooccurrence_affinity
from app.scoring.cooccurrence_store import read_cooccurrence
from app.scoring.engine import CandidateInput, rank
from app.scoring.live_lookup import bounded_lookup, skipped_lookup
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
    # CLAUDE.md 참고)이고, 방향을 붙여 제안 쪽 보정값과 섞이지 않게 한다.
    cluster_key = lift_key(
        MatchDirection.TEAM_TO_USER, team_cluster_key(recruiting_roles, team_contest_field)
    )

    # 이 방향에서는 팀이 속한 공모전이 기준점이고, 후보(사용자)의 상호작용 이력이 비교 대상이다
    # — 계산 함수 자체는 양방향이 그대로 공유한다. 팀 공모전이 없거나 상호작용 이력이 있는 후보가
    # 하나도 없으면 Supabase를 부르지 않는다. 기준점이 공모전 하나라 그 이웃 전체를 읽는다(후보들이 본
    # 공모전을 다 합치면 이웃 목록보다 길어지기 쉽다).
    team_event_id = as_event_id(request.query_metadata.get("event_id"))
    candidate_interactions = {
        c.candidate_id: as_event_ids(c.metadata.get("interacted_event_ids", []))
        for c in request.candidates
    }
    cooccurrence_lookup = (
        bounded_lookup(read_cooccurrence, [team_event_id])
        if team_event_id is not None and any(candidate_interactions.values())
        else skipped_lookup()
    )
    cluster_lifts, cooccurrence = await asyncio.gather(
        bounded_lookup(read_cluster_lifts),
        cooccurrence_lookup,
    )
    weights = adjust_weights(WEIGHTS, cluster_lifts.get(cluster_key, {}))

    candidates = []
    label_context = {}
    # 선택 필드(activity_time) 점수는 metadata_scores와 분리해서 들고 있는다 — WEIGHTS에 없는
    # 키가 섞이면 label_for()의 근거 선택을 흐릴 수 있다.
    optional_scores = {}
    for candidate in request.candidates:
        similarity = cosine_similarity(request.query_embedding_vector, candidate.embedding_vector)
        desired_roles = candidate.metadata.get("desired_roles", [])
        skills = candidate.metadata.get("skills", [])
        candidate_style = candidate.metadata.get("activity_style")
        candidate_experience = candidate.metadata.get("experience_level")
        metadata_scores = {
            "role_match": role_match_score(recruiting_roles, desired_roles),
            "deficit_fit": deficit_fit_score(required_skills, skills),
            "activity_style_match": activity_style_match_score(team_activity_style, candidate_style),
            "beginner_fit": beginner_fit_score(candidate_experience, team_beginner_friendly),
            "cf_affinity": cooccurrence_affinity(
                candidate_interactions[candidate.candidate_id], team_event_id, cooccurrence
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
            "matched_roles": matched_items(recruiting_roles, desired_roles),
            "matched_skills": matched_items(required_skills, skills),
            "activity_style": candidate_style,
            "beginner_friendly": team_beginner_friendly,
            "seeker_is_beginner": candidate_experience == "beginner",
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
