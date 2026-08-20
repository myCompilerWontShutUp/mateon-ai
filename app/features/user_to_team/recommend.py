import asyncio

from app.features.user_to_team.scoring import (
    PENALTY_RULES,
    WEIGHTS,
    deficit_fit_score,
    label_for,
    role_match_score,
)
from app.schemas.recommendation import RecommendationItem, RecommendationRequest, RecommendationResponse
from app.scoring.cluster import user_cluster_key
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


async def recommend_teams(request: RecommendationRequest) -> RecommendationResponse:
    desired_roles = request.query_metadata.get("desired_roles", [])
    skills = request.query_metadata.get("skills", [])
    activity_style = request.query_metadata.get("activity_style")
    experience_level = request.query_metadata.get("experience_level")
    activity_time = request.query_metadata.get("activity_time")

    # 1번 항목(오프라인 클러스터 가중치 보정) — 라이브 서버는 계산하지 않고 배치가 미리 써둔
    # 값을 읽기만 한다. Supabase 조회는 동기 클라이언트라 이벤트 루프를 막지 않게 스레드에서
    # 실행하고, 실패하면 read_cluster_lifts()가 빈 dict를 돌려줘 기본 WEIGHTS로 안전하게
    # 후퇴한다(사용자 응답은 이 조회 실패로 절대 막히지 않는다).
    cluster_key = user_cluster_key(desired_roles, experience_level)
    cluster_lifts = await asyncio.to_thread(read_cluster_lifts)
    weights = adjust_weights(WEIGHTS, cluster_lifts.get(cluster_key, {}))

    candidates = []
    label_context = {}
    # 선택 필드(activity_time) 점수는 metadata_scores와 분리해서 들고 있는다 — WEIGHTS에 없는
    # 키가 metadata_scores에 섞이면 label_for()의 "가장 점수가 높은 컴포넌트" 판단이 이 값을
    # 잘못 집어갈 수 있다(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 4번 참고).
    optional_scores = {}
    for candidate in request.candidates:
        similarity = cosine_similarity(request.query_embedding_vector, candidate.embedding_vector)
        candidate_style = candidate.metadata.get("activity_style")
        candidate_beginner_friendly = candidate.metadata.get("beginner_friendly")
        metadata_scores = {
            "role_match": role_match_score(
                desired_roles, candidate.metadata.get("recruiting_roles", [])
            ),
            "deficit_fit": deficit_fit_score(
                skills, candidate.metadata.get("required_skills", [])
            ),
            "activity_style_match": activity_style_match_score(activity_style, candidate_style),
            "beginner_fit": beginner_fit_score(experience_level, candidate_beginner_friendly),
        }
        candidates.append(
            CandidateInput(
                candidate_id=candidate.candidate_id,
                raw_similarity=similarity,
                metadata_scores=metadata_scores,
            )
        )
        label_context[candidate.candidate_id] = {
            "matched_roles": matched_items(desired_roles, candidate.metadata.get("recruiting_roles", [])),
            "matched_skills": matched_items(candidate.metadata.get("required_skills", []), skills),
            "activity_style": candidate_style,
            "beginner_friendly": candidate_beginner_friendly,
        }
        optional_scores[candidate.candidate_id] = {
            "activity_time_match": activity_time_match_score(
                activity_time, candidate.metadata.get("activity_time")
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
