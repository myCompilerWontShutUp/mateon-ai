import base64

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.prompts import load_prompt
from app.openai_client.extraction import extract_structured
from app.schemas.contest import ContestExtractionResult

_SYSTEM_PROMPT = load_prompt("contest_image_extraction")

_SUPPORTED_IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def resolve_image_mime_type(filename: str | None) -> str:
    extension = "." + filename.rsplit(".", 1)[-1].lower() if filename and "." in filename else ""
    mime_type = _SUPPORTED_IMAGE_MIME_TYPES.get(extension)
    if mime_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="img_file must have one of these extensions: .jpg, .jpeg, .png",
        )
    return mime_type


async def extract_contest_from_image(img_file: UploadFile) -> ContestExtractionResult:
    mime_type = resolve_image_mime_type(img_file.filename)
    image_bytes = await img_file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="img_file is empty")

    settings = get_settings()
    if len(image_bytes) > settings.max_contest_image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"img_file exceeds the {settings.max_contest_image_bytes} byte limit",
        )

    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"

    return await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "이 공고 이미지를 스키마에 맞게 정리해줘."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        response_model=ContestExtractionResult,
    )
