import hashlib

import pymupdf
import pytest

from app.features.portfolio_summary import summary
from app.schemas.llm_output import PortfolioSummaryText


def _build_pdf_bytes(page_count: int) -> bytes:
    with pymupdf.open() as document:
        for _ in range(page_count):
            document.new_page()
        return document.tobytes()


def test_validate_pdf_upload_rejects_non_pdf_extension() -> None:
    with pytest.raises(Exception):
        summary.validate_pdf_upload("resume.docx", b"whatever")


def test_validate_pdf_upload_rejects_empty_bytes() -> None:
    with pytest.raises(Exception):
        summary.validate_pdf_upload("portfolio.pdf", b"")


def test_validate_pdf_upload_accepts_pdf_within_limit() -> None:
    summary.validate_pdf_upload("portfolio.pdf", _build_pdf_bytes(1))


def test_render_pdf_pages_to_data_urls_returns_one_data_url_per_page() -> None:
    pdf_bytes = _build_pdf_bytes(3)
    data_urls = summary.render_pdf_pages_to_data_urls(pdf_bytes, max_pages=10)
    assert len(data_urls) == 3
    assert all(url.startswith("data:image/png;base64,") for url in data_urls)


def test_render_pdf_pages_to_data_urls_caps_at_max_pages() -> None:
    pdf_bytes = _build_pdf_bytes(5)
    data_urls = summary.render_pdf_pages_to_data_urls(pdf_bytes, max_pages=2)
    assert len(data_urls) == 2


def test_render_pdf_pages_to_data_urls_rejects_invalid_pdf_bytes() -> None:
    with pytest.raises(Exception):
        summary.render_pdf_pages_to_data_urls(b"not a pdf", max_pages=10)


class _FakeUploadFile:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


@pytest.fixture(autouse=True)
def _mock_extract_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract_structured(messages, response_model) -> PortfolioSummaryText:
        return PortfolioSummaryText(response="- 프로젝트 A\n\n요약\n요약 문단입니다.")

    monkeypatch.setattr(summary, "extract_structured", fake_extract_structured)


async def test_summarize_portfolio_pdf_returns_sha256_of_input_bytes() -> None:
    pdf_bytes = _build_pdf_bytes(1)
    upload = _FakeUploadFile("portfolio.pdf", pdf_bytes)

    result = await summary.summarize_portfolio_pdf(upload)

    assert result.pdf_id == hashlib.sha256(pdf_bytes).hexdigest()
    assert "요약" in result.response
