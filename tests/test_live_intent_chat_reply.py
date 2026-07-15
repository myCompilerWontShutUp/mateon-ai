"""실제 OpenAI 호출로 챗봇 재질문 응답이 4가지 규칙을 지키는지 확인한다.

규칙 원문은 prompts/user_intent_chat_reply.txt 참고. 정확한 문구는 매번 달라지므로
구조적 신호(질문 형태인지, 방어 문구인지, 코드 값이 그대로 노출되지 않는지)만 검증한다.
"""

import pytest

from app.features.user_to_team.chat_reply import generate_intent_chat_reply
from app.schemas.user_intent import UserIntentFields


@pytest.mark.live
async def test_no_missing_field_restates_and_moves_to_recommendation() -> None:
    extracted = UserIntentFields(desired_roles=["BE"], experience_level="advanced")
    reply = await generate_intent_chat_reply(
        extracted, next_missing_field=None, latest_message="백엔드 실무 3년차입니다."
    )

    assert "BE" not in reply, "역할 코드가 자연어로 번역되지 않고 그대로 노출됐다"
    assert "?" not in reply, "누락 필드가 없는데도 추가 질문을 하고 있다"


@pytest.mark.live
async def test_one_missing_field_asks_only_that_field() -> None:
    extracted = UserIntentFields(desired_roles=["BE"])
    reply = await generate_intent_chat_reply(
        extracted, next_missing_field="experience_level", latest_message="저는 백엔드가 좋아요."
    )

    assert "BE" not in reply
    assert "?" in reply, "다음 항목을 유도 질문 형태로 물어야 한다"


@pytest.mark.live
async def test_off_topic_message_triggers_defensive_reply() -> None:
    extracted = UserIntentFields(desired_roles=["BE"])
    reply = await generate_intent_chat_reply(
        extracted, next_missing_field="experience_level", latest_message="오늘 날씨 진짜 좋다."
    )

    assert "이해" in reply, "전혀 무관한 답변엔 방어 문구('이해하지 못했다' 류)로 반응해야 한다"
