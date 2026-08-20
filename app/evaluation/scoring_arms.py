"""Hit@10 평가(2번 항목)에서 비교하는 4개 랭킹 방법 중 앞 3개를 구현한다(단순추론은 LLM 호출이라
`scripts/run_eval.py`에 직접 둔다). 임베딩+메타데이터/+보정모델 두 방법은 실제 프로덕션
스코어링 로직(`app/features/user_to_team/scoring.py`, `app/scoring/engine.py`)을 그대로
재사용한다 — 평가가 실제 서비스 동작을 정확히 반영하게 하기 위해 재구현하지 않는다.
"""

from app.features.user_to_team.scoring import PENALTY_RULES, WEIGHTS, deficit_fit_score, role_match_score
from app.scoring.cluster_weights import adjust_weights
from app.scoring.engine import CandidateInput, CandidateScore, rank
from app.scoring.rules import activity_style_match_score, beginner_fit_score
from app.scoring.similarity import cosine_similarity


def embedding_only_ranking(user_vector: list[float], teams: dict) -> list[int]:
    """비교군 1: 순수 코사인 유사도만으로 정렬 — 메타데이터 룰 스코어링을 전혀 쓰지 않는다."""
    scored = [
        (int(team_id), cosine_similarity(user_vector, team["embedding_vector"]))
        for team_id, team in teams.items()
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [team_id for team_id, _ in scored]


def _build_candidates(user_vector: list[float], user_metadata: dict, teams: dict) -> list[CandidateInput]:
    desired_roles = user_metadata.get("desired_roles", [])
    skills = user_metadata.get("skills", [])
    activity_style = user_metadata.get("activity_style")
    experience_level = user_metadata.get("experience_level")

    candidates = []
    for team_id, team in teams.items():
        meta = team["metadata"]
        similarity = cosine_similarity(user_vector, team["embedding_vector"])
        metadata_scores = {
            "role_match": role_match_score(desired_roles, meta.get("recruiting_roles", [])),
            "deficit_fit": deficit_fit_score(skills, meta.get("required_skills", [])),
            "activity_style_match": activity_style_match_score(activity_style, meta.get("activity_style")),
            "beginner_fit": beginner_fit_score(experience_level, meta.get("beginner_friendly")),
        }
        candidates.append(
            CandidateInput(candidate_id=int(team_id), raw_similarity=similarity, metadata_scores=metadata_scores)
        )
    return candidates


def production_ranking(user_vector: list[float], user_metadata: dict, teams: dict) -> list[CandidateScore]:
    """비교군 2: 실제 프로덕션 스코어링(임베딩 유사도 + 역할 일치도/결핍 보완도/활동 방식
    일치도/초보자 적합도, WEIGHTS·PENALTY_RULES 그대로)."""
    candidates = _build_candidates(user_vector, user_metadata, teams)
    return rank(candidates, WEIGHTS, PENALTY_RULES)


def corrected_ranking(
    user_vector: list[float],
    user_metadata: dict,
    teams: dict,
    cluster_lifts: dict[str, float],
) -> list[CandidateScore]:
    """비교군 3: 프로덕션 스코어링 + 클러스터별 가중치 보정(보정모델). 컴포넌트 점수는 그대로
    두고 `WEIGHTS`만 클러스터별 lift에 비례해 재분배한다(`adjust_weights`) — 점수를 건드리지
    않으므로 1.0 상한에 의한 변별력 손실이 없다."""
    candidates = _build_candidates(user_vector, user_metadata, teams)
    adjusted_weights = adjust_weights(WEIGHTS, cluster_lifts)
    return rank(candidates, adjusted_weights, PENALTY_RULES)
