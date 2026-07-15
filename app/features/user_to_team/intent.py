from app.features.user_to_team.chat_reply import generate_intent_chat_reply
from app.features.user_to_team.extraction import extract_user_intent_fields
from app.features.user_to_team.template import compute_missing_fields, render_intent_embedding_text
from app.openai_client.embedding import embed_text
from app.schemas.user_intent import UserIntentExtractionRequest, UserIntentExtractionResult


def _build_context(request: UserIntentExtractionRequest) -> str:
    return "\n".join(m.message for m in request.messages)


async def compute_user_intent(request: UserIntentExtractionRequest) -> UserIntentExtractionResult:
    context = _build_context(request)
    fields = await extract_user_intent_fields(context)
    missing_fields = compute_missing_fields(fields)
    latest_message = request.messages[-1].message
    next_missing_field = missing_fields[0] if missing_fields else None
    assistant_message = await generate_intent_chat_reply(fields, next_missing_field, latest_message)

    if missing_fields:
        return UserIntentExtractionResult(
            missing_fields=missing_fields, extracted=fields, assistant_message=assistant_message
        )

    embedding_text = render_intent_embedding_text(context, fields)
    embedding_vector = await embed_text(embedding_text)
    return UserIntentExtractionResult(
        missing_fields=[],
        extracted=fields,
        embedding_text=embedding_text,
        embedding_vector=embedding_vector,
        assistant_message=assistant_message,
    )
