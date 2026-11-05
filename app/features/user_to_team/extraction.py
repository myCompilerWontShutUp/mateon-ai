from app.core.prompts import load_prompt
from app.openai_client.extraction import extract_structured
from app.schemas.activity import activity_style_prompt_listing
from app.schemas.role_codes import role_code_prompt_listing
from app.schemas.user_intent import UserIntentFields

_SYSTEM_PROMPT = (
    load_prompt("user_intent_extraction")
    + f"\n\n역할 코드 목록(공모전 도메인별):\n{role_code_prompt_listing()}"
    # 헷갈리기 쉬운 표현의 구분 규칙 — 팀 추출과 같은 파일을 써야 양쪽이 같은 코드로 정규화된다.
    + f"\n\n{load_prompt('role_code_rules')}"
    + f"\n\n활동 방식 코드 목록: {activity_style_prompt_listing()}"
)


async def extract_user_intent_fields(context: str) -> UserIntentFields:
    return await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        response_model=UserIntentFields,
    )
