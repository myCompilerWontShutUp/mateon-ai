import pytest

from app.features.user_to_team import intent as intent_module
from app.schemas.user_intent import ConversationMessage, UserIntentExtractionRequest, UserIntentFields


async def test_incomplete_intent_skips_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract(context: str) -> UserIntentFields:
        return UserIntentFields(skills=["React"])  # desired_roles/experience_level 없음

    embed_called = False

    async def fake_embed(text: str) -> list[float]:
        nonlocal embed_called
        embed_called = True
        return [0.0] * 1536

    async def fake_chat_reply(extracted, next_missing_field, latest_message) -> str:
        return "챗봇 응답 placeholder"

    monkeypatch.setattr(intent_module, "extract_user_intent_fields", fake_extract)
    monkeypatch.setattr(intent_module, "embed_text", fake_embed)
    monkeypatch.setattr(intent_module, "generate_intent_chat_reply", fake_chat_reply)

    request = UserIntentExtractionRequest(
        messages=[ConversationMessage(id=1, message="아직 뭘 원하는지 잘 모르겠어요.")]
    )
    result = await intent_module.compute_user_intent(request)

    assert set(result.missing_fields) == {"desired_roles", "experience_level"}
    assert result.embedding_text is None
    assert result.embedding_vector is None
    assert embed_called is False  # 미완성 슬롯은 임베딩 비용을 쓰지 않는다
    assert result.assistant_message == "챗봇 응답 placeholder"


async def test_complete_intent_computes_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract(context: str) -> UserIntentFields:
        return UserIntentFields(desired_roles=["BE"], experience_level="beginner")

    async def fake_embed(text: str) -> list[float]:
        return [0.1] * 1536

    async def fake_chat_reply(extracted, next_missing_field, latest_message) -> str:
        return "챗봇 응답 placeholder"

    monkeypatch.setattr(intent_module, "extract_user_intent_fields", fake_extract)
    monkeypatch.setattr(intent_module, "embed_text", fake_embed)
    monkeypatch.setattr(intent_module, "generate_intent_chat_reply", fake_chat_reply)

    request = UserIntentExtractionRequest(
        messages=[ConversationMessage(id=1, message="백엔드를 해보고 싶습니다.")]
    )
    result = await intent_module.compute_user_intent(request)

    assert result.missing_fields == []
    assert result.embedding_text is not None
    assert len(result.embedding_vector) == 1536
