import asyncio

from app.features.user_to_team.scoring import (
    PENALTY_RULES,
    WEIGHTS,
    deficit_fit_score,
    label_for,
    role_match_score,
)
from app.schemas.common import MatchDirection
from app.schemas.recommendation import RecommendationItem, RecommendationRequest, RecommendationResponse
from app.scoring.behavior_blend import blend_query_vector
from app.scoring.cluster import lift_key, user_cluster_key
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


async def recommend_teams(request: RecommendationRequest) -> RecommendationResponse:
    desired_roles = request.query_metadata.get("desired_roles", [])
    skills = request.query_metadata.get("skills", [])
    activity_style = request.query_metadata.get("activity_style")
    experience_level = request.query_metadata.get("experience_level")
    activity_time = request.query_metadata.get("activity_time")

    # 1번 항목(오프라인 클러스터 가중치 보정) — 라이브 서버는 계산하지 않고 배치가 미리 써둔
    # 값을 읽기만 한다. 조회가 실패하거나 몇 초 안에 끝나지 않으면 기본 WEIGHTS로 진행한다
    # (app/scoring/live_lookup.py). 키에 방향을 붙여 역제안 쪽 보정값과 섞이지 않게 한다
    # (app/scoring/cluster.py의 lift_key).
    cluster_key = lift_key(
        MatchDirection.USER_TO_TEAM, user_cluster_key(desired_roles, experience_level)
    )

    # 사용자가 북마크/지원한 공모전 목록 — BE가 안 보내면 CF 점수가 전부 0이 되고, 그러면
    # 총점이 기존의 단조 변환이라 순위가 그대로다(cf_affinity 가중치 주석 참고).
    interacted_event_ids = as_event_ids(request.query_metadata.get("interacted_event_ids", []))
    # CF는 "사용자가 본 공모전"과 "후보 팀의 공모전"이 둘 다 있어야 계산된다 — 하나라도 없으면
    # Supabase를 아예 부르지 않고, 있으면 후보 팀 공모전과 사용자가 본 공모전 사이의 쌍만 읽는다.
    target_event_ids = {as_event_id(c.metadata.get("event_id")) for c in request.candidates} - {None}
    cooccurrence_lookup = (
        bounded_lookup(read_cooccurrence, target_event_ids, interacted_event_ids)
        if interacted_event_ids and target_event_ids
        else skipped_lookup()
    )
    # 클러스터 lift(가중치 보정)와 동시발생 행렬(CF)은 서로 독립이라 동시에 조회한다.
    cluster_lifts, cooccurrence = await asyncio.gather(
        bounded_lookup(read_cluster_lifts),
        cooccurrence_lookup,
    )
    weights = adjust_weights(WEIGHTS, cluster_lifts.get(cluster_key, {}))

    # 행동 이력이 있으면 intent 벡터에 섞어 개인화한다 — 없으면(BE 미연동 포함) intent를 그대로
    # 쓰므로 기존 동작과 완전히 같다. 협업 필터링이 아니라 콘텐츠 기반 개인화다
    # (app/scoring/behavior_blend.py 참고).
    query_vector = blend_query_vector(
        request.query_embedding_vector,
        request.behavior_embedding_vector,
        request.interaction_count,
    )

    # 라벨이 초보자 문구를 쓸지 판단하는 데 쓴다 — 경험 수준을 모르면 초보자로 보지 않는다
    # (beginner_fit_score와 같은 기준).
    seeker_is_beginner = experience_level == "beginner"

    candidates = []
    label_context = {}
    # 선택 필드(activity_time) 점수는 metadata_scores와 분리해서 들고 있는다 — WEIGHTS에 없는
    # 키가 metadata_scores에 섞이면 label_for()의 근거 선택이 이 값을 잘못 집어갈 수 있다
    # (CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 4번 참고).
    optional_scores = {}
    for candidate in request.candidates:
        similarity = cosine_similarity(query_vector, candidate.embedding_vector)
        recruiting_roles = candidate.metadata.get("recruiting_roles", [])
        required_skills = candidate.metadata.get("required_skills", [])
        candidate_style = candidate.metadata.get("activity_style")
        candidate_beginner_friendly = candidate.metadata.get("beginner_friendly")
        metadata_scores = {
            "role_match": role_match_score(desired_roles, recruiting_roles),
            "deficit_fit": deficit_fit_score(skills, required_skills),
            "activity_style_match": activity_style_match_score(activity_style, candidate_style),
            "beginner_fit": beginner_fit_score(experience_level, candidate_beginner_friendly),
            # 이 저장소에서 유일한 협업 신호 — 텍스트를 전혀 보지 않고 "같은 사람들이 무엇을
            # 함께 봤는가"만으로 계산된다(app/scoring/cooccurrence.py).
            "cf_affinity": cooccurrence_affinity(
                interacted_event_ids, candidate.metadata.get("event_id"), cooccurrence
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
            "matched_roles": matched_items(desired_roles, recruiting_roles),
            "matched_skills": matched_items(required_skills, skills),
            "activity_style": candidate_style,
            "beginner_friendly": candidate_beginner_friendly,
            "seeker_is_beginner": seeker_is_beginner,
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
