"""LLM-as-judge(scripts/judge_outputs.judge)가 실제로 판별력이 있는지 확인한다.

정상 텍스트는 통과시키고, 설계 원칙(절대평가 금지/ID·점수 미언급/컨텍스트 일치)을 어긴
텍스트는 잡아내야 한다. 이 판별력 자체가 회귀하지 않았는지 지키는 테스트다.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.judge_outputs import judge  # noqa: E402

_CONTEXT = (
    "지원자 요약: 실무 3년차 백엔드 개발자, Spring Boot/Kafka 능숙, 핀테크 관심\n"
    "팀 요약: 핀테크 가계부 서비스, BE 1명 결핍, Spring Boot/Kafka/Redis 요구"
)


@pytest.mark.live
async def test_judge_passes_compliant_text() -> None:
    text = (
        "summary: 실무 백엔드 경험을 바탕으로 이 팀의 BE 결핍을 보완하고 싶습니다.\n"
        "message: 핀테크 가계부 서비스의 기술 스택이 제 경험과 잘 맞아 지원합니다. 함께 성장하고 싶습니다."
    )
    verdict = await judge("user_to_team_proposal", _CONTEXT, text)
    assert verdict.passes, f"정상 텍스트인데 위반 판정: {verdict.violations}"


@pytest.mark.live
async def test_judge_catches_absolute_evaluation() -> None:
    text = (
        "summary: 이 지원자는 매우 뛰어나고 훌륭한 실력을 가진 우수한 개발자입니다.\n"
        "message: 최고의 인재이므로 반드시 합류시켜야 합니다."
    )
    verdict = await judge("user_to_team_proposal", _CONTEXT, text)
    assert not verdict.passes
    assert verdict.violations


@pytest.mark.live
async def test_judge_catches_id_and_score_leak() -> None:
    text = (
        "summary: user_id 203번 지원자는 synergy_score 0.91로 이 팀에 매우 적합합니다.\n"
        "message: team_id 17번 팀에 지원하고 싶습니다."
    )
    verdict = await judge("user_to_team_proposal", _CONTEXT, text)
    assert not verdict.passes
    assert verdict.violations
