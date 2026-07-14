from app.features.user_to_team.extraction import extract_user_intent_fields
from app.features.user_to_team.template import compute_missing_fields, render_intent_embedding_text
from app.openai_client.embedding import embed_text
from app.schemas.user_intent import UserIntentExtractionRequest, UserIntentExtractionResult


def _build_context(request: UserIntentExtractionRequest) -> str:
    parts = [f"자기소개서: {request.self_introduction}"]
    if request.profile:
        parts.append(f"프로필: {request.profile}")
    if request.conversation_answers:
        parts.append(f"추가 답변: {request.conversation_answers}")
    return "\n".join(parts)


async def compute_user_intent(request: UserIntentExtractionRequest) -> UserIntentExtractionResult:
    fields = await extract_user_intent_fields(_build_context(request))
    missing_fields = compute_missing_fields(fields)

    if missing_fields:
        return UserIntentExtractionResult(missing_fields=missing_fields, extracted=fields)

    embedding_text = render_intent_embedding_text(request.self_introduction, fields)
    embedding_vector = await embed_text(embedding_text)
    return UserIntentExtractionResult(
        missing_fields=[],
        extracted=fields,
        embedding_text=embedding_text,
        embedding_vector=embedding_vector,
    )
