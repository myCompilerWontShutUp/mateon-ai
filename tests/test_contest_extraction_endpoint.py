import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.features.contest_extraction import router as router_module
from app.schemas.contest import ContestCategory, ContestExtractionResult, ContestField

_AUTH_HEADERS = {"X-Internal-Secret": get_settings().internal_shared_secret}
_FAKE_RESULT = ContestExtractionResult(
    category=ContestCategory.CONTEST,
    field=ContestField.PLANNING_IDEA,
    title="2026 아이디어 공모전",
)


@pytest.fixture(autouse=True)
def _mock_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract_contest_from_image(img_file) -> ContestExtractionResult:
        return _FAKE_RESULT

    monkeypatch.setattr(
        router_module, "extract_contest_from_image", fake_extract_contest_from_image
    )


def _files(filename: str = "poster.png") -> dict:
    return {"img_file": (filename, b"fake-image-bytes", "image/png")}


async def test_extract_image_without_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/contests/extract-image", files=_files())
    assert response.status_code == 422  # missing required header


async def test_extract_image_with_wrong_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/contests/extract-image", files=_files(), headers={"X-Internal-Secret": "wrong"}
    )
    assert response.status_code == 401


async def test_extract_image_without_file_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/contests/extract-image", headers=_AUTH_HEADERS)
    assert response.status_code == 422


async def test_extract_image_with_correct_secret_succeeds(client: AsyncClient) -> None:
    response = await client.post(
        "/contests/extract-image", files=_files(), headers=_AUTH_HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "2026 아이디어 공모전"
    assert body["category"] == "CONTEST"
    assert body["field"] == "PLANNING_IDEA"
