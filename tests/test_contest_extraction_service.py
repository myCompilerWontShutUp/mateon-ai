import pytest

from app.features.contest_extraction import extraction
from app.schemas.contest import ContestCategory, ContestExtractionResult, ContestField


class _FakeUploadFile:
    def __init__(self, filename: str | None, content: bytes) -> None:
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


@pytest.fixture(autouse=True)
def _mock_extract_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract_structured(messages, response_model) -> ContestExtractionResult:
        return ContestExtractionResult(
            category=ContestCategory.CONTEST, field=ContestField.ETC, title="테스트 공모전"
        )

    monkeypatch.setattr(extraction, "extract_structured", fake_extract_structured)


async def test_extract_contest_from_image_rejects_empty_file() -> None:
    upload = _FakeUploadFile("poster.png", b"")
    with pytest.raises(Exception):
        await extraction.extract_contest_from_image(upload)


async def test_extract_contest_from_image_rejects_unsupported_extension() -> None:
    upload = _FakeUploadFile("poster.bmp", b"fake-bytes")
    with pytest.raises(Exception):
        await extraction.extract_contest_from_image(upload)


async def test_extract_contest_from_image_returns_mocked_result() -> None:
    upload = _FakeUploadFile("poster.png", b"fake-image-bytes")

    result = await extraction.extract_contest_from_image(upload)

    assert result.title == "테스트 공모전"
    assert result.category == ContestCategory.CONTEST


async def test_extract_contest_from_image_embeds_image_as_data_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    async def fake_extract_structured(messages, response_model) -> ContestExtractionResult:
        captured["messages"] = messages
        return ContestExtractionResult(
            category=ContestCategory.CONTEST, field=ContestField.ETC, title="x"
        )

    monkeypatch.setattr(extraction, "extract_structured", fake_extract_structured)

    upload = _FakeUploadFile("poster.jpg", b"fake-image-bytes")
    await extraction.extract_contest_from_image(upload)

    user_message = captured["messages"][1]
    image_block = next(
        part for part in user_message["content"] if part["type"] == "image_url"
    )
    assert image_block["image_url"]["url"].startswith("data:image/jpeg;base64,")
