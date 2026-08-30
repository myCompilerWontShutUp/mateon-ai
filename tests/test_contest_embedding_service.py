import pytest

from app.features.contest_embedding import service
from app.schemas.contest_embedding import ContestEmbeddingRefreshRequest


@pytest.fixture(autouse=True)
def _mock_embed_text(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_embed_text(text: str) -> list[float]:
        return [0.1] * 1536

    monkeypatch.setattr(service, "embed_text", fake_embed_text)


async def test_compute_contest_embedding_echoes_event_id_without_storing_anything() -> None:
    request = ContestEmbeddingRefreshRequest(
        event_id=337930,
        title="경기도 1인가구 정책제안 아이디어 공모전",
        description="경기도 1인가구를 위한 정책 아이디어를 공모합니다.",
    )

    result = await service.compute_contest_embedding(request)

    assert result.event_id == 337930
    assert len(result.embedding_vector) == 1536
    assert not hasattr(result, "title")
    assert not hasattr(result, "description")
