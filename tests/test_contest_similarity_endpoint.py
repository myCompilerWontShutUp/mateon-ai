from httpx import AsyncClient

from app.core.config import get_settings

_VECTOR = [1.0] + [0.0] * 1535


def _payload() -> dict:
    return {
        "query": {"id": "q1", "embedding_vector": _VECTOR, "title": "쿼리 공모전"},
        "candidates": [
            {"id": "c1", "embedding_vector": _VECTOR, "title": "후보 공모전"},
        ],
    }


async def test_similarity_map_without_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/contests/similarity-map", json=_payload())
    assert response.status_code == 422  # missing required header


async def test_similarity_map_with_wrong_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/contests/similarity-map", json=_payload(), headers={"X-Internal-Secret": "wrong"}
    )
    assert response.status_code == 401


async def test_similarity_map_with_correct_secret_succeeds(client: AsyncClient) -> None:
    secret = get_settings().internal_shared_secret
    response = await client.post(
        "/contests/similarity-map", json=_payload(), headers={"X-Internal-Secret": secret}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["query"]["id"] == "q1"
    assert len(body["points"]) == 1
    assert body["points"][0]["id"] == "c1"


async def test_similarity_map_rejects_wrong_dimension_vector(client: AsyncClient) -> None:
    secret = get_settings().internal_shared_secret
    payload = _payload()
    payload["query"]["embedding_vector"] = [1.0, 2.0]  # not 1536-dim
    response = await client.post(
        "/contests/similarity-map", json=payload, headers={"X-Internal-Secret": secret}
    )
    assert response.status_code == 422
