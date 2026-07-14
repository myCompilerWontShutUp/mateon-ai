import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.features.team_embedding import router as router_module
from app.schemas.embedding import EmbeddingResult

_PAYLOAD = {
    "intro_text": "커머스 플랫폼을 만드는 팀입니다.",
    "recruiting_roles": ["BE"],
    "required_skills": ["Spring Boot"],
}


@pytest.fixture(autouse=True)
def _mock_compute(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_compute_team_embedding(request) -> EmbeddingResult:
        return EmbeddingResult(embedding_text="...", embedding_vector=[0.1] * 1536)

    monkeypatch.setattr(router_module, "compute_team_embedding", fake_compute_team_embedding)


async def test_refresh_without_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/internal/teams/embedding:refresh", json=_PAYLOAD)
    assert response.status_code == 422  # missing required header


async def test_refresh_with_wrong_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/teams/embedding:refresh",
        json=_PAYLOAD,
        headers={"X-Internal-Secret": "wrong"},
    )
    assert response.status_code == 401


async def test_refresh_with_correct_secret_succeeds(client: AsyncClient) -> None:
    secret = get_settings().internal_shared_secret
    response = await client.post(
        "/internal/teams/embedding:refresh",
        json=_PAYLOAD,
        headers={"X-Internal-Secret": secret},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["embedding_vector"]) == 1536
    assert "team_id" not in body
