from app.openai_client.extraction import extract_structured
from app.schemas.team_extraction import TeamSoftFields

_SYSTEM_PROMPT = (
    "너는 팀 소개 텍스트에서 활동 목표, 활동 방식, 활동 강도, 초보자 환영 여부, 팀 분위기를 "
    "추출하는 도우미다. 텍스트에 명시적으로 드러나지 않는 항목은 추측하지 말고 null로 남겨라."
)


async def extract_team_soft_fields(intro_text: str) -> TeamSoftFields:
    return await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": intro_text},
        ],
        response_model=TeamSoftFields,
    )
