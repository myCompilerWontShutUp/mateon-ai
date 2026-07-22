import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.features.portfolio_summary import router as router_module
from app.schemas.portfolio import PortfolioSummaryResult

_AUTH_HEADERS = {"X-Internal-Secret": get_settings().internal_shared_secret}
_FAKE_RESULT = PortfolioSummaryResult(pdf_id="a" * 64, response="- 프로젝트 1\n\n요약\n요약 문단")


@pytest.fixture(autouse=True)
def _mock_summarize(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_summarize_portfolio_pdf(pdf_file) -> PortfolioSummaryResult:
        return _FAKE_RESULT

    monkeypatch.setattr(router_module, "summarize_portfolio_pdf", fake_summarize_portfolio_pdf)


def _files(filename: str = "portfolio.pdf") -> dict:
    return {"pdf_file": (filename, b"%PDF-fake", "application/pdf")}


async def test_summarize_without_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/portfolios/summarize", files=_files())
    assert response.status_code == 422  # missing required header


async def test_summarize_with_wrong_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/portfolios/summarize", files=_files(), headers={"X-Internal-Secret": "wrong"}
    )
    assert response.status_code == 401


async def test_summarize_without_file_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/portfolios/summarize", headers=_AUTH_HEADERS)
    assert response.status_code == 422


async def test_summarize_with_correct_secret_succeeds(client: AsyncClient) -> None:
    response = await client.post(
        "/portfolios/summarize", files=_files(), headers=_AUTH_HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pdf_id"] == "a" * 64
    assert "요약" in body["response"]
