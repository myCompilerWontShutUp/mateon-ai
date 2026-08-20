"""실 `cluster_selection_events`가 쌓이기 전까지 2번/3번 항목(Hit@10 평가, 클러스터 가중치
보정)을 시연하기 위한 가상 시나리오 — **실 데이터가 아니다.** "실제 사용자 선호가 현재
프로덕션 가중치와는 다르게, 활동 방식 일치도·초보자 적합도를 더 중시한다"는 가정을 고정된
대체 가중치로 표현한다. `scripts/generate_eval_synthetic_selections.py`(합성 선택 이벤트 생성)와
`scripts/run_eval.py`(보정 효과를 직접 측정하는 "선호 회복률" 지표) 양쪽에서 재사용한다.
"""

from app.scoring.engine import CandidateScore

# 프로덕션 WEIGHTS(similarity=0.4, role_match=0.2, deficit_fit=0.15, beginner_fit=0.2,
# activity_style_match=0.05)와 의도적으로 다르게 잡았다.
SIMULATED_TRUE_PREFERENCE_WEIGHTS = {
    "similarity": 0.25,
    "role_match": 0.2,
    "deficit_fit": 0.15,
    "beginner_fit": 0.25,
    "activity_style_match": 0.15,
}


def true_preference_score(candidate_score: CandidateScore) -> float:
    scores = {"similarity": candidate_score.similarity, **candidate_score.metadata_scores}
    return sum(
        SIMULATED_TRUE_PREFERENCE_WEIGHTS[name] * scores[name]
        for name in SIMULATED_TRUE_PREFERENCE_WEIGHTS
    )
