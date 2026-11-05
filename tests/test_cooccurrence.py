from app.scoring.cooccurrence import build_cooccurrence, cooccurrence_affinity


def _interactions(pairs: list[tuple[int, int]]) -> list[dict]:
    return [{"user_id": user_id, "event_id": event_id} for user_id, event_id in pairs]


def test_events_seen_by_the_same_users_are_linked() -> None:
    # 유저 1, 2가 공모전 10과 20을 모두 봤다.
    cooc = build_cooccurrence(_interactions([(1, 10), (1, 20), (2, 10), (2, 20)]))

    assert cooc[10][20] == 1.0
    assert cooc[20][10] == 1.0  # 대칭


def test_pairs_below_min_co_users_are_dropped() -> None:
    """한 명만 겹치는 쌍은 우연일 수 있어 버린다."""
    cooc = build_cooccurrence(_interactions([(1, 10), (1, 20)]))

    assert cooc == {}


def test_duplicate_interactions_by_same_user_are_counted_once() -> None:
    """같은 사용자가 북마크와 지원을 둘 다 해도 가중치가 두 배가 되면 안 된다."""
    doubled = build_cooccurrence(
        _interactions([(1, 10), (1, 10), (1, 20), (2, 10), (2, 20), (2, 20)])
    )
    single = build_cooccurrence(_interactions([(1, 10), (1, 20), (2, 10), (2, 20)]))

    assert doubled == single


def test_popular_event_does_not_dominate_everything() -> None:
    """인기 편향 제거(코사인 정규화) — 모두가 보는 공모전이 모든 것과 강하게 연결돼 보이면 안 된다."""
    # 공모전 10은 유저 4명 모두가 봤고, 20과 30은 각각 2명씩만 봤다.
    interactions = _interactions(
        [(1, 10), (2, 10), (3, 10), (4, 10), (1, 20), (2, 20), (3, 30), (4, 30)]
    )

    cooc = build_cooccurrence(interactions)

    # 20과 30을 함께 본 사람은 없지만, 둘 다 인기 공모전 10과는 겹친다.
    assert cooc[10][20] < 1.0
    assert 30 not in cooc.get(20, {})


def test_affinity_picks_strongest_link_not_the_average() -> None:
    """관심사가 넓은 사용자도 변별력을 잃지 않도록 평균이 아니라 최댓값을 쓴다."""
    cooc = {99: {10: 0.9, 20: 0.1}}

    assert cooccurrence_affinity([10, 20], 99, cooc) == 0.9


def test_affinity_is_zero_without_data() -> None:
    """저장소가 비었거나 처음 보는 공모전이면 0 — 모든 후보가 같은 값을 받아 순위에 영향이 없다."""
    assert cooccurrence_affinity([10], 99, {}) == 0.0
    assert cooccurrence_affinity([], 99, {99: {10: 0.9}}) == 0.0
    assert cooccurrence_affinity([10], None, {99: {10: 0.9}}) == 0.0


def test_affinity_ignores_the_event_the_user_already_saw() -> None:
    """이미 본 공모전의 팀을 연관도 최고점으로 올리는 건 추천이 아니라 되풀이다."""
    cooc = {10: {10: 1.0, 20: 0.4}}

    assert cooccurrence_affinity([10], 10, cooc) == 0.0


def test_affinity_accepts_string_event_ids() -> None:
    """요청 metadata는 자유 dict라 ID가 문자열로 올 수 있다 — 조용히 0점이 되면 안 된다."""
    cooccurrence = {300: {100: 0.8}}

    assert cooccurrence_affinity(["100"], "300", cooccurrence) == 0.8
    assert cooccurrence_affinity(["abc", None], "300", cooccurrence) == 0.0
