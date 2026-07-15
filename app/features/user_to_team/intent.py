from app.features.user_to_team.chat_reply import generate_intent_chat_reply
from app.features.user_to_team.extraction import extract_user_intent_fields
from app.features.user_to_team.template import compute_missing_fields, render_intent_embedding_text
from app.openai_client.embedding import embed_text
from app.schemas.user_intent import UserIntentExtractionRequest, UserIntentExtractionResult


def _build_context(request: UserIntentExtractionRequest) -> str:
    # AI의 질문과 사용자의 답변을 번갈아 보여줘야 짧은 답변("없어", "평범한 것 같아")도
    # 직전 질문의 맥락에서 해석할 수 있다 — 사용자 발화만 이어붙이면 문맥이 사라진다.
    speaker = {"user": "사용자", "assistant": "AI"}
    return "\n".join(f"{speaker[m.role]}: {m.message}" for m in request.messages)


def _latest_user_message(request: UserIntentExtractionRequest) -> str:
    for message in reversed(request.messages):
        if message.role == "user":
            return message.message
    return request.messages[-1].message


def _user_only_text(request: UserIntentExtractionRequest) -> str:
    # 임베딩은 사용자의 의도를 대변해야 하므로 AI의 정형화된 질문 문구(모든 사용자에게 공통으로
    # 섞여 들어가면 임베딩의 변별력을 흐린다)는 빼고 사용자가 실제로 한 말만 모은다.
    return "\n".join(m.message for m in request.messages if m.role == "user")


async def compute_user_intent(request: UserIntentExtractionRequest) -> UserIntentExtractionResult:
    context = _build_context(request)
    fields = await extract_user_intent_fields(context)
    missing_fields = compute_missing_fields(fields)
    latest_message = _latest_user_message(request)
    next_missing_field = missing_fields[0] if missing_fields else None
    assistant_message = await generate_intent_chat_reply(fields, next_missing_field, latest_message)

    if missing_fields:
        return UserIntentExtractionResult(
            missing_fields=missing_fields, extracted=fields, assistant_message=assistant_message
        )

    embedding_text = render_intent_embedding_text(_user_only_text(request), fields)
    embedding_vector = await embed_text(embedding_text)
    return UserIntentExtractionResult(
        missing_fields=[],
        extracted=fields,
        embedding_text=embedding_text,
        embedding_vector=embedding_vector,
        assistant_message=assistant_message,
    )
