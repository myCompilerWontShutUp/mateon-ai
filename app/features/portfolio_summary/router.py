from fastapi import APIRouter, Depends, File, UploadFile

from app.api.internal_auth import require_internal_secret
from app.features.portfolio_summary.summary import summarize_portfolio_pdf
from app.schemas.portfolio import PortfolioSummaryResult

router = APIRouter(tags=["portfolio-summary"], dependencies=[Depends(require_internal_secret)])


@router.post("/portfolios/summarize", summary="포트폴리오 PDF OCR+LLM 경력 요약")
async def summarize_portfolio(pdf_file: UploadFile = File(...)) -> PortfolioSummaryResult:
    return await summarize_portfolio_pdf(pdf_file)
