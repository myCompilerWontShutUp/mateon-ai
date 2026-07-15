"""실제 OpenAI 호출로 여러 턴에 걸친 재질문 흐름이 끝까지 수렴하는지 확인한다.

AI의 질문(role=assistant)을 messages에 같이 재전송하지 않으면, "없는거같아"/
"평범한거같은데" 같은 짧고 모호한 답변이 무엇에 대한 답인지 알 수 없어
missing_fields가 영영 안 비고 같은 질문이 반복되는 버그가 실제로 있었다
(2026-07-15, 실제 시뮬레이션에서 재현됨). 이 테스트는 그 회귀를 막는다.
"""

import pytest

from app.features.user_to_team.intent import compute_user_intent
from app.schemas.user_intent import ConversationMessage, UserIntentExtractionRequest


@pytest.mark.live
async def test_vague_reply_resolves_when_prior_question_is_in_context() -> None:
    messages = [
        ConversationMessage(id=1, role="assistant", message="개발 경험이나 실력 수준이 어때?"),
        ConversationMessage(id=2, role="user", message="없는거같아"),
    ]
    result = await compute_user_intent(UserIntentExtractionRequest(messages=messages))

    assert result.extracted.experience_level == "beginner", (
        f"직전 질문(개발 경험)과 함께 주면 '없는거같아'가 beginner로 해석돼야 한다: "
        f"{result.extracted.experience_level!r}"
    )


@pytest.mark.live
async def test_multi_turn_conversation_converges_to_no_missing_fields() -> None:
    turns = [
        ("assistant", "안녕! 나는 드림이야, 너한테 딱 맞는 팀을 찾아주는 도우미야. 먼저 너에 대해 간단히 소개해줄래?"),
        ("user", "재밌는 공모전을 찾고 있습니다."),
    ]
    messages = [
        ConversationMessage(id=i + 1, role=role, message=msg) for i, (role, msg) in enumerate(turns)
    ]

    for user_reply in ["기획에 관심이 있어", "없는거같아"]:
        result = await compute_user_intent(UserIntentExtractionRequest(messages=messages))
        messages.append(
            ConversationMessage(id=len(messages) + 1, role="assistant", message=result.assistant_message)
        )
        messages.append(ConversationMessage(id=len(messages) + 1, role="user", message=user_reply))

    final = await compute_user_intent(UserIntentExtractionRequest(messages=messages))

    assert final.missing_fields == [], (
        f"3턴 안에 필수 정보가 다 채워져야 하는데 여전히 누락됨: {final.missing_fields}"
    )
    assert final.extracted.desired_roles == ["PM"]
    assert final.extracted.experience_level == "beginner"
