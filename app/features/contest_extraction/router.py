from fastapi import APIRouter, Depends, File, UploadFile

from app.api.internal_auth import require_internal_secret
from app.features.contest_extraction.extraction import extract_contest_from_image
from app.schemas.contest import ContestExtractionResult

router = APIRouter(tags=["contest-extraction"], dependencies=[Depends(require_internal_secret)])


@router.post("/contests/extract-image", summary="공모전 이미지 OCR+LLM 자동 입력")
async def extract_image_to_contest(img_file: UploadFile = File(...)) -> ContestExtractionResult:
    return await extract_contest_from_image(img_file)
