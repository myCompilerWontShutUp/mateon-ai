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


def test_build_context_includes_assistant_turns_for_short_answer_disambiguation() -> None:
    # 회귀 테스트: AI의 질문이 컨텍스트에서 빠지면 "없는거같아" 같은 짧은 답변이 무엇에 대한
    # 답인지 알 수 없어 experience_level이 영영 안 채워지는 버그가 실제로 있었다(2026-07-15).
    request = UserIntentExtractionRequest(
        messages=[
            ConversationMessage(id=1, role="assistant", message="개발 경험이 있어?"),
            ConversationMessage(id=2, role="user", message="없는거같아"),
        ]
    )
    context = intent_module._build_context(request)

    assert "AI: 개발 경험이 있어?" in context
    assert "사용자: 없는거같아" in context


def test_latest_user_message_skips_assistant_turns() -> None:
    request = UserIntentExtractionRequest(
        messages=[
            ConversationMessage(id=1, role="user", message="백엔드가 좋아요"),
            ConversationMessage(id=2, role="assistant", message="경험은 어때?"),
        ]
    )
    assert intent_module._latest_user_message(request) == "백엔드가 좋아요"


async def test_embedding_text_excludes_assistant_boilerplate(monkeypatch: pytest.MonkeyPatch) -> None:
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
        messages=[
            ConversationMessage(id=1, role="assistant", message="안녕! 나는 드림이야."),
            ConversationMessage(id=2, role="user", message="백엔드를 해보고 싶습니다."),
        ]
    )
    result = await intent_module.compute_user_intent(request)

    assert "드림이" not in result.embedding_text
    assert "백엔드를 해보고 싶습니다." in result.embedding_text
