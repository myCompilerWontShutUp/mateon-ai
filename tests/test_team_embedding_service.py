import pytest

from app.features.team_embedding import service
from app.schemas.team_extraction import TeamEmbeddingRefreshRequest, TeamSoftFields


@pytest.fixture(autouse=True)
def _mock_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract_team_soft_fields(intro_text: str) -> TeamSoftFields:
        return TeamSoftFields(
            activity_goal="공모전 수상",
            activity_style="주 2회 오프라인",
            activity_intensity="high",
            beginner_friendly=True,
            team_atmosphere="자유로운 분위기",
        )

    async def fake_embed_text(text: str) -> list[float]:
        return [0.1] * 1536

    monkeypatch.setattr(service, "extract_team_soft_fields", fake_extract_team_soft_fields)
    monkeypatch.setattr(service, "embed_text", fake_embed_text)


async def test_compute_team_embedding_returns_result_without_storing_anything() -> None:
    request = TeamEmbeddingRefreshRequest(
        intro_text="커머스 플랫폼을 만드는 팀입니다.",
        recruiting_roles=["BE"],
        required_skills=["Spring Boot"],
    )

    result = await service.compute_team_embedding(request)

    assert result.missing_fields == []
    assert len(result.embedding_vector) == 1536
    assert result.metadata["recruiting_roles"] == ["BE"]
    assert not hasattr(result, "team_id")
    assert not hasattr(result, "last_embedded_at")
