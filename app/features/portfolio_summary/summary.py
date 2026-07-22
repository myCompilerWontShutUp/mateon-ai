import base64
import hashlib

import pymupdf
from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.prompts import load_prompt
from app.openai_client.extraction import extract_structured
from app.schemas.llm_output import PortfolioSummaryText
from app.schemas.portfolio import PortfolioSummaryResult

_SYSTEM_PROMPT = load_prompt("portfolio_summary")
# 2.0 = 144 DPI 상당 — 스캔된 텍스트도 vision 모델이 읽을 수 있는 해상도면서 파일당 이미지
# 용량은 과도하게 키우지 않는 절충값.
_RENDER_ZOOM = 2.0


def validate_pdf_upload(filename: str | None, pdf_bytes: bytes) -> None:
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="pdf_file must have a .pdf extension"
        )
    if not pdf_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pdf_file is empty")

    settings = get_settings()
    if len(pdf_bytes) > settings.max_portfolio_pdf_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"pdf_file exceeds the {settings.max_portfolio_pdf_bytes} byte limit",
        )


def render_pdf_pages_to_data_urls(pdf_bytes: bytes, max_pages: int) -> list[str]:
    matrix = pymupdf.Matrix(_RENDER_ZOOM, _RENDER_ZOOM)
    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
            if document.page_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="pdf_file has no pages"
                )
            data_urls = []
            for page in document[:max_pages]:
                pixmap = page.get_pixmap(matrix=matrix)
                encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
                data_urls.append(f"data:image/png;base64,{encoded}")
            return data_urls
    except pymupdf.FileDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="pdf_file is not a valid PDF"
        ) from exc


async def summarize_portfolio_pdf(pdf_file: UploadFile) -> PortfolioSummaryResult:
    pdf_bytes = await pdf_file.read()
    validate_pdf_upload(pdf_file.filename, pdf_bytes)

    settings = get_settings()
    page_data_urls = render_pdf_pages_to_data_urls(pdf_bytes, settings.portfolio_pdf_max_pages)

    content: list[dict] = [{"type": "text", "text": "이 포트폴리오를 읽고 경력 사항을 정리해줘."}]
    content.extend({"type": "image_url", "image_url": {"url": url}} for url in page_data_urls)

    text_result = await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_model=PortfolioSummaryText,
    )

    pdf_id = hashlib.sha256(pdf_bytes).hexdigest()
    return PortfolioSummaryResult(pdf_id=pdf_id, response=text_result.response)
