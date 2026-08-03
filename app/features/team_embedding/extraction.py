from app.core.prompts import load_prompt
from app.openai_client.extraction import extract_structured
from app.schemas.contest import CONTEST_FIELD_LABELS
from app.schemas.role_codes import role_code_prompt_listing
from app.schemas.team_extraction import TeamSoftFields

_ROLE_CODE_LISTING = role_code_prompt_listing()
_CONTEST_FIELD_LISTING = ", ".join(
    f"{field.value}({label})" for field, label in CONTEST_FIELD_LABELS.items()
)
_SYSTEM_PROMPT = (
    load_prompt("team_soft_fields_extraction")
    + f"\n\n역할 코드 목록: {_ROLE_CODE_LISTING}"
    + f"\n공모전/행사 분야 코드 목록: {_CONTEST_FIELD_LISTING}"
)


async def extract_team_soft_fields(
    intro_text: str, recruiting_roles: list[str], contest_field: str | None
) -> TeamSoftFields:
    context = (
        f"팀 소개: {intro_text}\n"
        f"모집 역할(원문): {', '.join(recruiting_roles) or '없음'}\n"
        f"공모전/행사 분야(원문): {contest_field or '없음'}"
    )
    return await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        response_model=TeamSoftFields,
    )
