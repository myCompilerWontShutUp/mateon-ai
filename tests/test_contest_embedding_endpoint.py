import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.features.contest_embedding import router as router_module
from app.schemas.contest_embedding import ContestEmbeddingResult

_PAYLOAD = {
    "event_id": 337930,
    "title": "경기도 1인가구 정책제안 아이디어 공모전",
    "description": "경기도 1인가구를 위한 정책 아이디어를 공모합니다.",
}


@pytest.fixture(autouse=True)
def _mock_compute(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_compute_contest_embedding(request) -> ContestEmbeddingResult:
        return ContestEmbeddingResult(event_id=request.event_id, embedding_vector=[0.1] * 1536)

    monkeypatch.setattr(router_module, "compute_contest_embedding", fake_compute_contest_embedding)


async def test_refresh_without_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/internal/contests/embedding:refresh", json=_PAYLOAD)
    assert response.status_code == 422  # missing required header


async def test_refresh_with_wrong_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/contests/embedding:refresh",
        json=_PAYLOAD,
        headers={"X-Internal-Secret": "wrong"},
    )
    assert response.status_code == 401


async def test_refresh_with_correct_secret_succeeds(client: AsyncClient) -> None:
    secret = get_settings().internal_shared_secret
    response = await client.post(
        "/internal/contests/embedding:refresh",
        json=_PAYLOAD,
        headers={"X-Internal-Secret": secret},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == 337930
    assert len(body["embedding_vector"]) == 1536
