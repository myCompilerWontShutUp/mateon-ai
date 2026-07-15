from app.core.prompts import load_prompt
from app.openai_client.extraction import extract_structured
from app.schemas.team_extraction import TeamSoftFields

_SYSTEM_PROMPT = load_prompt("team_soft_fields_extraction")


async def extract_team_soft_fields(intro_text: str) -> TeamSoftFields:
    return await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": intro_text},
        ],
        response_model=TeamSoftFields,
    )
