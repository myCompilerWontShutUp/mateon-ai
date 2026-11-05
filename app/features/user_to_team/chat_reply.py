from app.core.prompts import load_prompt
from app.openai_client.extraction import extract_structured
from app.schemas.activity import activity_style_label
from app.schemas.llm_output import UserIntentChatReply
from app.schemas.role_codes import role_code_translation_guide
from app.schemas.user_intent import UserIntentFields

_SYSTEM_PROMPT = (
    load_prompt("user_intent_chat_reply") + f"\n역할 코드→한글 라벨: {role_code_translation_guide()}"
)

AI_PERSONA_NAME = "드림이"

# 대화 시작 시 클라이언트가 사용자의 첫 메시지보다 먼저 보여줘야 하는 인사말이다.
# /intents/extract는 최소 1개의 메시지를 요구하므로(UserIntentExtractionRequest.messages),
# 이 인사말 자체는 API 호출 없이 클라이언트가 그대로 표시한다 — 아직 추출할 사용자 발화가
# 없어서 LLM이 생성할 이유도 없다(결정론적 고정 문구). 사용자가 여기에 답하면 그 답변이
# messages의 첫 번째 항목이 되고, 그때부터 일반적인 재질문 흐름(rules 1~4)이 시작된다.
# missing_fields가 있든 없든(즉 곧바로 추천이 가능하든 아니든) 이 인사말이 항상 먼저 나온다.
OPENING_GREETING = (
    f"안녕! 나는 {AI_PERSONA_NAME}야, 너한테 딱 맞는 팀을 찾아주는 도우미야. "
    "먼저 너에 대해 간단히 소개해줄래? 어떤 역할을 하고 싶은지, 관심 분야나 경험이 있다면 "
    "편하게 말해줘!"
)

_FIELD_LABELS = {
    # 분야와 무관하게 쓰이는 문구여야 한다 — 이전엔 "개발 경험/실력 수준"이라 요리·문학 공모전
    # 사용자에게도 개발 경험을 묻게 됐다. 역할은 도메인별로 나뉘어 있어 분야도 함께 묻는다.
    "desired_roles": "참여하고 싶은 공모전 분야와 그 안에서 맡고 싶은 역할",
    "experience_level": "그 분야에서의 경험/실력 수준",
    "activity_style": "선호하는 활동 방식",
    "activity_goal": "이번 활동으로 이루고 싶은 목표",
}


def _build_chat_context(
    extracted: UserIntentFields, next_missing_field: str | None, latest_message: str
) -> str:
    known = []
    if extracted.desired_roles:
        known.append(f"희망 역할: {', '.join(extracted.desired_roles)}")
    if extracted.skills:
        known.append(f"스킬: {', '.join(extracted.skills)}")
    if extracted.interests:
        known.append(f"관심 분야: {', '.join(extracted.interests)}")
    if extracted.optional.activity_goal:
        known.append(f"활동 목표: {extracted.optional.activity_goal}")
    if extracted.activity_style:
        # 코드(ONLINE)를 그대로 넘기면 챗봇이 문장에 코드 값을 노출할 수 있어 한글 라벨로 넘긴다
        # (역할 코드는 프롬프트의 번역 가이드가 처리한다).
        known.append(f"활동 방식: {activity_style_label(extracted.activity_style)}")
    if extracted.experience_level:
        known.append(f"경험 수준: {extracted.experience_level}")

    next_label = _FIELD_LABELS.get(next_missing_field, next_missing_field) if next_missing_field else None

    lines = [
        "지금까지 파악된 정보: " + ("; ".join(known) if known else "아직 없음"),
        "다음에 물어봐야 할 항목: " + (next_label or "없음(모든 필수 정보가 채워짐)"),
        f"사용자가 방금 보낸 메시지: {latest_message}",
    ]
    return "\n".join(lines)


async def generate_intent_chat_reply(
    extracted: UserIntentFields, next_missing_field: str | None, latest_message: str
) -> str:
    context = _build_chat_context(extracted, next_missing_field, latest_message)
    reply = await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        response_model=UserIntentChatReply,
    )
    return reply.message
