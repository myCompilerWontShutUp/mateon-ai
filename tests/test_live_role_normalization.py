"""실제 OpenAI 호출로 역할/경험 수준 코드 정규화가 지켜지는지 확인한다.

한때 LLM이 desired_roles를 '백엔드 개발자'처럼 자연어로 뱉어 팀의 recruiting_roles
("BE")와 매칭이 안 되는 문제가 있었다(prompts/user_intent_extraction.txt에서 고침).
이 테스트는 그 회귀를 막는다.
"""

import pytest

from app.features.user_to_team.extraction import extract_user_intent_fields

_ALLOWED_ROLES = {"BE", "FE", "Design", "PM", "Data"}
_ALLOWED_EXPERIENCE_LEVELS = {"beginner", "intermediate", "advanced"}


@pytest.mark.live
async def test_desired_roles_are_normalized_to_codes() -> None:
    fields = await extract_user_intent_fields(
        "저는 3년차 백엔드 개발자입니다. Spring Boot를 씁니다."
    )

    assert fields.desired_roles, "desired_roles가 비어있으면 안 된다"
    assert set(fields.desired_roles) <= _ALLOWED_ROLES, (
        f"코드로 정규화되지 않은 역할이 섞였다: {fields.desired_roles}"
    )
    assert "BE" in fields.desired_roles


@pytest.mark.live
async def test_experience_level_is_normalized_to_code() -> None:
    fields = await extract_user_intent_fields(
        "저는 완전 초보자입니다. 코딩을 배운 지 한 달밖에 안 됐습니다."
    )

    assert fields.experience_level in _ALLOWED_EXPERIENCE_LEVELS, (
        f"경험 수준이 코드로 정규화되지 않았다: {fields.experience_level!r}"
    )
    assert fields.experience_level == "beginner"
