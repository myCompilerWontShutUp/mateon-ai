import math

from app.features.contest_similarity.service import compute_contest_similarity
from app.schemas.contest_similarity import ContestSimilarityItem, ContestSimilarityRequest


def _item(id_: str, vector: list[float], field: str | None = None) -> ContestSimilarityItem:
    return ContestSimilarityItem(
        id=id_,
        embedding_vector=vector,
        title=f"공모전 {id_}",
        organizer="주최자",
        category="CONTEST",
        field=field,
        detail_url=f"https://example.com/{id_}",
    )


def _vector(*, first: float) -> list[float]:
    # cosine_similarity(query, candidate)가 first에 비례해서 나오도록 만든 간단한 벡터.
    return [first] + [1.0] * 1535


async def test_more_similar_candidate_gets_smaller_radius() -> None:
    request = ContestSimilarityRequest(
        query=_item("query", _vector(first=10.0)),
        candidates=[
            _item("close", _vector(first=9.0)),
            _item("far", _vector(first=0.1)),
        ],
    )

    response = await compute_contest_similarity(request)
    by_id = {p.id: p for p in response.points}

    assert by_id["close"].similarity > by_id["far"].similarity
    assert by_id["close"].radius < by_id["far"].radius
    assert by_id["close"].rank_percentile < by_id["far"].rank_percentile


async def test_top_n_cuts_candidate_pool() -> None:
    candidates = [_item(f"c{i}", _vector(first=float(i))) for i in range(10)]
    request = ContestSimilarityRequest(
        query=_item("query", _vector(first=5.5)), candidates=candidates, top_n=3
    )

    response = await compute_contest_similarity(request)

    assert len(response.points) == 3
    assert response.candidate_pool_total == 10


async def test_different_rank_bands_never_overlap_in_radius() -> None:
    """회귀 테스트 — 반지름 지터가 순위 대역을 넘어 겹치던 실제 버그(2026-08-23, 사용자
    스크린샷으로 발견)를 다시 잡아낸다. 상위 20%의 최대 거리가 하위 20%의 최소 거리보다 항상
    작아야 한다."""
    candidates = [_item(f"c{i}", _vector(first=float(i))) for i in range(50)]
    request = ContestSimilarityRequest(query=_item("query", _vector(first=100.0)), candidates=candidates)

    response = await compute_contest_similarity(request)
    ranked = sorted(response.points, key=lambda p: -p.similarity)
    distances = [math.hypot(p.x, p.y) for p in ranked]

    n = len(distances)
    top20_max = max(distances[: n // 5])
    bottom20_min = min(distances[-(n // 5) :])

    assert top20_max < bottom20_min


async def test_reference_rings_reflect_actual_similarity_at_percentile() -> None:
    candidates = [_item(f"c{i}", _vector(first=float(i))) for i in range(20)]
    request = ContestSimilarityRequest(query=_item("query", _vector(first=100.0)), candidates=candidates)

    response = await compute_contest_similarity(request)

    assert len(response.reference_rings) == 4
    percentiles = [ring.percentile for ring in response.reference_rings]
    assert percentiles == sorted(percentiles)
    for ring in response.reference_rings:
        assert 0.0 <= ring.similarity_at_percentile <= 1.0
        assert response.min_radius <= ring.radius <= response.max_radius


async def test_field_label_derived_from_normalized_code() -> None:
    request = ContestSimilarityRequest(
        query=_item("query", _vector(first=5.0), field="EDUCATION"),
        candidates=[_item("c1", _vector(first=4.0), field="COOKING_FOOD")],
    )

    response = await compute_contest_similarity(request)

    assert response.query.field_label == "교육"
    assert response.points[0].field_label == "요리/식품"


async def test_unknown_field_code_echoes_without_label() -> None:
    request = ContestSimilarityRequest(
        query=_item("query", _vector(first=5.0)),
        candidates=[_item("c1", _vector(first=4.0), field="NOT_A_REAL_CODE")],
    )

    response = await compute_contest_similarity(request)

    assert response.points[0].field == "NOT_A_REAL_CODE"
    assert response.points[0].field_label == "NOT_A_REAL_CODE"


async def test_empty_candidates_returns_empty_points_and_rings() -> None:
    request = ContestSimilarityRequest(query=_item("query", _vector(first=5.0)), candidates=[])

    response = await compute_contest_similarity(request)

    assert response.points == []
    assert response.reference_rings == []
    assert response.candidate_pool_total == 0
