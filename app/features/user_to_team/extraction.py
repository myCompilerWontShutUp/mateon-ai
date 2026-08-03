from app.core.prompts import load_prompt
from app.openai_client.extraction import extract_structured
from app.schemas.role_codes import role_code_prompt_listing
from app.schemas.user_intent import UserIntentFields

_SYSTEM_PROMPT = (
    load_prompt("user_intent_extraction") + f"\n\n역할 코드 목록: {role_code_prompt_listing()}"
)


async def extract_user_intent_fields(context: str) -> UserIntentFields:
    return await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        response_model=UserIntentFields,
    )
