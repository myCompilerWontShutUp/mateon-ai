from app.evaluation.metrics import graded_ndcg_at_k, hit_at_k, ndcg_at_k


def test_hit_at_k_true_when_relevant_in_top_k() -> None:
    assert hit_at_k([5, 3, 1, 9], {1, 2}, k=3) == 1.0


def test_hit_at_k_false_when_relevant_outside_top_k() -> None:
    assert hit_at_k([5, 3, 9, 1], {1}, k=2) == 0.0


def test_hit_at_k_zero_when_no_relevant_ids() -> None:
    assert hit_at_k([5, 3, 1], set(), k=3) == 0.0


def test_ndcg_perfect_when_all_relevant_at_top() -> None:
    # 정답이 2개고 top-2에 둘 다 있으면 이상적인 순서와 같아 NDCG == 1.0
    assert ndcg_at_k([1, 2, 3], {1, 2}, k=3) == 1.0


def test_ndcg_lower_when_relevant_ranked_later() -> None:
    high = ndcg_at_k([1, 3, 4], {1}, k=3)
    low = ndcg_at_k([3, 4, 1], {1}, k=3)
    assert high > low


def test_ndcg_zero_when_no_relevant_ids() -> None:
    assert ndcg_at_k([1, 2, 3], set(), k=3) == 0.0


def test_ndcg_discriminates_between_saturated_hit_at_k() -> None:
    # 둘 다 Hit@3 == 1.0(정답이 top-3 안에 있음)이지만 순위가 다르면 NDCG는 달라야 한다 —
    # 이게 바로 "Hit@10만으로는 변별력이 떨어진다"는 CLAUDE.md 서술의 근거.
    relevant = {7}
    ranked_best = [7, 1, 2]
    ranked_worst = [1, 2, 7]

    assert hit_at_k(ranked_best, relevant, k=3) == hit_at_k(ranked_worst, relevant, k=3) == 1.0
    assert ndcg_at_k(ranked_best, relevant, k=3) > ndcg_at_k(ranked_worst, relevant, k=3)


def test_graded_ndcg_perfect_when_ranked_by_relevance_desc() -> None:
    # 관련성 점수가 높은 순서(7 > 3)대로 그대로 랭킹돼 있으면 이상적인 순서와 같다.
    relevance = {7: 0.9, 3: 0.4, 1: 0.0}
    assert graded_ndcg_at_k([7, 3, 1], relevance, k=3) == 1.0


def test_graded_ndcg_lower_when_low_relevance_item_ranked_first() -> None:
    relevance = {7: 0.9, 3: 0.4}
    best = graded_ndcg_at_k([7, 3], relevance, k=2)
    worst = graded_ndcg_at_k([3, 7], relevance, k=2)
    assert best > worst


def test_graded_ndcg_zero_when_relevance_empty() -> None:
    assert graded_ndcg_at_k([1, 2, 3], {}, k=3) == 0.0


def test_graded_ndcg_ignores_ids_outside_relevance_dict() -> None:
    # relevance에 없는 id(비정답 후보)는 0점 취급 — 순위에 끼어 있어도 dcg에 기여하지 않는다.
    relevance = {7: 1.0}
    assert graded_ndcg_at_k([99, 7], relevance, k=2) < graded_ndcg_at_k([7, 99], relevance, k=2)


def test_precision_at_k_counts_relevant_share_of_top_k() -> None:
    from app.evaluation.metrics import precision_at_k

    assert precision_at_k([1, 2, 3, 4], {1, 3}, k=3) == 2 / 3


def test_precision_at_k_counts_missing_slots_as_misses() -> None:
    """추천을 k개보다 적게 낸 방법이 유리해지면 안 된다."""
    from app.evaluation.metrics import precision_at_k

    assert precision_at_k([1], {1}, k=3) == 1 / 3


def test_wilson_interval_contains_point_estimate_and_stays_in_unit_range() -> None:
    from app.evaluation.metrics import wilson_interval

    low, high = wilson_interval(45, 100)
    assert low < 0.45 < high
    # 경계값은 수학적으로 정확히 0·1이지만 부동소수점 오차가 남으므로 허용 오차로 비교한다.
    assert abs(wilson_interval(0, 11)[0]) < 1e-12
    assert abs(wilson_interval(11, 11)[1] - 1.0) < 1e-12


def test_wilson_interval_is_wider_for_small_samples() -> None:
    from app.evaluation.metrics import wilson_interval

    small_low, small_high = wilson_interval(5, 11)
    big_low, big_high = wilson_interval(45, 100)
    assert (small_high - small_low) > (big_high - big_low)
