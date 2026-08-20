from app.scoring.cluster_weights import adjust_weights, compute_weight_lifts


def _event(cluster_key: str, selected_id: int, shown: list[tuple[int, dict]]) -> dict:
    return {
        "chooser_cluster_key": cluster_key,
        "selected_candidate_id": selected_id,
        "shown_candidates": [
            {"candidate_id": cid, "component_scores": scores} for cid, scores in shown
        ],
    }


def test_positive_lift_is_recorded() -> None:
    events = [
        _event("BE:beginner", 1, [(1, {"beginner_fit": 1.0}), (2, {"beginner_fit": 0.0})]),
        _event("BE:beginner", 3, [(3, {"beginner_fit": 1.0}), (4, {"beginner_fit": 0.0})]),
    ]

    lifts = compute_weight_lifts(events, components=["beginner_fit"])

    # 선택된 쪽 평균(1.0) - 전체 평균(0.5) = lift 0.5
    assert lifts["BE:beginner"]["beginner_fit"] == 0.5


def test_negative_lift_is_ignored() -> None:
    events = [
        _event("FE:advanced", 1, [(1, {"role_match": 0.0}), (2, {"role_match": 1.0})]),
        _event("FE:advanced", 3, [(3, {"role_match": 0.0}), (4, {"role_match": 1.0})]),
    ]

    lifts = compute_weight_lifts(events, components=["role_match"])

    assert "FE:advanced" not in lifts


def test_sparse_cluster_below_min_events_is_skipped() -> None:
    events = [_event("Design:beginner", 1, [(1, {"similarity": 1.0}), (2, {"similarity": 0.0})])]

    lifts = compute_weight_lifts(events, components=["similarity"], min_events=2)

    assert lifts == {}


def test_adjust_weights_no_lift_returns_base_unchanged() -> None:
    base = {"similarity": 0.4, "role_match": 0.2}
    assert adjust_weights(base, {}) == base


def test_adjust_weights_boosts_lifted_component_and_conserves_total() -> None:
    base = {"similarity": 0.4, "role_match": 0.2, "beginner_fit": 0.2, "deficit_fit": 0.15, "activity_style_match": 0.05}

    adjusted = adjust_weights(base, {"beginner_fit": 1.0}, gain=1.0)

    # beginner_fit의 상대 비중이 늘어야 한다.
    assert adjusted["beginner_fit"] > base["beginner_fit"]
    # 다른 컴포넌트는 상대적으로 줄어야 한다(총합 보존을 위해).
    assert adjusted["similarity"] < base["similarity"]
    # 총합은 그대로 보존된다(스코어 스케일이 프로덕션과 비교 가능하게 유지).
    assert abs(sum(adjusted.values()) - sum(base.values())) < 1e-9


def test_adjust_weights_does_not_touch_component_scores() -> None:
    # cluster_weights 모듈에는 이제 점수에 손대는 함수가 없다 — apply_bonuses는 제거됐다.
    import app.scoring.cluster_weights as module

    assert not hasattr(module, "apply_bonuses")
