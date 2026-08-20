import pytest

from app.features.user_to_team import proposal as proposal_module
from app.schemas.common import MatchDirection
from app.schemas.llm_output import ProposalTextFields
from app.schemas.proposal import ProposalAssemblyRequest, SelectionContext, ShownCandidate


async def test_assemble_user_to_team_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract_structured(messages, response_model) -> ProposalTextFields:
        return ProposalTextFields(summary="BE 결핍 보완에 적합합니다.", message="지원합니다!")

    monkeypatch.setattr(proposal_module, "extract_structured", fake_extract_structured)

    request = ProposalAssemblyRequest(
        user_id=203,
        team_id=17,
        contest_id=5,
        sender_id=203,
        receiver_id=17,
        intent_id=88,
        synergy_score=0.91,
        candidate_summary="React/TypeScript 경험, 초보자",
        target_summary="커머스 플랫폼, BE 1명 결핍",
    )

    result = await proposal_module.assemble_user_to_team_proposal(request)

    assert result.direction == MatchDirection.USER_TO_TEAM
    assert result.user_id == 203
    assert result.team_id == 17
    assert result.synergy_score == 0.91
    assert result.portfolio_role_fit_score is None
    assert result.summary == "BE 결핍 보완에 적합합니다."


async def test_assemble_user_to_team_proposal_fires_judge_and_selection_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_extract_structured(messages, response_model) -> ProposalTextFields:
        return ProposalTextFields(summary="요약", message="메시지")

    monkeypatch.setattr(proposal_module, "extract_structured", fake_extract_structured)

    fired: list[str] = []

    def fake_fire_and_forget(coro) -> None:
        fired.append(coro.cr_code.co_name)
        coro.close()  # 실제로 실행하지 않는다 — 이 테스트는 배선만 검증한다.

    monkeypatch.setattr(proposal_module, "fire_and_forget", fake_fire_and_forget)

    request = ProposalAssemblyRequest(
        user_id=203,
        team_id=17,
        sender_id=203,
        receiver_id=17,
        synergy_score=0.91,
        candidate_summary="React/TypeScript 경험, 초보자",
        target_summary="커머스 플랫폼, BE 1명 결핍",
        selection_context=SelectionContext(
            idempotency_key="test-key-1",
            chooser_fields={"desired_roles": ["BE"], "experience_level": "beginner"},
            shown_candidates=[ShownCandidate(candidate_id=17, total_score=0.91, component_scores={})],
        ),
    )

    await proposal_module.assemble_user_to_team_proposal(request)

    assert fired == ["judge_and_log", "log_selection_event"]


async def test_assemble_user_to_team_proposal_skips_selection_log_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_extract_structured(messages, response_model) -> ProposalTextFields:
        return ProposalTextFields(summary="요약", message="메시지")

    monkeypatch.setattr(proposal_module, "extract_structured", fake_extract_structured)

    fired: list[str] = []

    def fake_fire_and_forget(coro) -> None:
        fired.append(coro.cr_code.co_name)
        coro.close()

    monkeypatch.setattr(proposal_module, "fire_and_forget", fake_fire_and_forget)

    request = ProposalAssemblyRequest(
        user_id=203,
        team_id=17,
        sender_id=203,
        receiver_id=17,
        synergy_score=0.91,
        candidate_summary="React/TypeScript 경험, 초보자",
        target_summary="커머스 플랫폼, BE 1명 결핍",
    )

    await proposal_module.assemble_user_to_team_proposal(request)

    assert fired == ["judge_and_log"]
