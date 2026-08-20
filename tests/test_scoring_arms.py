from app.evaluation.scoring_arms import corrected_ranking, embedding_only_ranking, production_ranking

_USER_VECTOR = [1.0, 0.0]

# 후보가 2개뿐이면 min-max 정규화가 원시 유사도 차이를 0~1로 최대치까지 벌려서 similarity
# 가중치(0.4)가 역할/스킬 일치(0.35 합)를 항상 이겨버린다(CLAUDE.md에 기록된 실제 현상) — 그
# 왜곡을 피하려고 후보 3개, 유사도 차이가 작은 값(1.0 vs 0.99)으로 구성한다.
_TEAMS = {
    "1": {
        "embedding_vector": [1.0, 0.0],  # 유사도 최고(1.0)지만 역할 불일치
        "metadata": {
            "recruiting_roles": ["FE"],
            "required_skills": [],
            "activity_style": None,
            "beginner_friendly": None,
        },
    },
    "2": {
        "embedding_vector": [0.99, 0.1410],  # 유사도 거의 동일(0.99), 역할·스킬 정확히 일치
        "metadata": {
            "recruiting_roles": ["BE"],
            "required_skills": ["Spring Boot"],
            "activity_style": None,
            "beginner_friendly": None,
        },
    },
    "3": {
        "embedding_vector": [0.0, 1.0],  # 유사도 낮고 역할도 불일치 — 순위표 채우기용
        "metadata": {
            "recruiting_roles": ["Design"],
            "required_skills": [],
            "activity_style": None,
            "beginner_friendly": None,
        },
    },
}

_USER_METADATA = {
    "desired_roles": ["BE"],
    "skills": ["Spring Boot"],
    "activity_style": None,
    "experience_level": "intermediate",
}


def test_embedding_only_ranks_by_raw_similarity() -> None:
    ranked = embedding_only_ranking(_USER_VECTOR, _TEAMS)
    assert ranked[0] == 1  # 유사도만 보면 team 1이 1위


def test_production_ranking_reuses_role_match_scoring() -> None:
    ranked = production_ranking(_USER_VECTOR, _USER_METADATA, _TEAMS)
    # team 2는 역할/스킬이 정확히 맞아서 메타데이터 점수가 team 1보다 훨씬 높다
    assert ranked[0].candidate_id == 2


def test_corrected_ranking_empty_lift_matches_production() -> None:
    without_lift = production_ranking(_USER_VECTOR, _USER_METADATA, _TEAMS)
    with_lift = corrected_ranking(_USER_VECTOR, _USER_METADATA, _TEAMS, cluster_lifts={})
    # lift가 없으면(빈 dict) adjust_weights가 base_weights를 그대로 돌려주므로 결과가 같아야 한다.
    assert [c.candidate_id for c in without_lift] == [c.candidate_id for c in with_lift]


def test_corrected_ranking_lift_boosts_component_leader_score() -> None:
    without_lift = production_ranking(_USER_VECTOR, _USER_METADATA, _TEAMS)
    with_lift = corrected_ranking(_USER_VECTOR, _USER_METADATA, _TEAMS, cluster_lifts={"deficit_fit": 1.0})

    scores_without = {c.candidate_id: c.total_score for c in without_lift}
    scores_with = {c.candidate_id: c.total_score for c in with_lift}
    # team 2는 deficit_fit=1.0(스킬 완전 일치)이라 그 가중치가 오르면 총점도 올라가야 한다 —
    # 점수 자체(1.0 상한)가 아니라 가중치 배분이 바뀌었기 때문(cluster_weights.py 수정 참고).
    assert scores_with[2] > scores_without[2]
    # 다른 컴포넌트의 가중치는 상대적으로 줄어드므로, deficit_fit이 0인 team 1/3은 점수가 내려간다.
    assert scores_with[1] < scores_without[1]
    assert scores_with[3] < scores_without[3]
