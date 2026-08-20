import pytest

from app.features.team_to_user import proposal as proposal_module
from app.schemas.common import MatchDirection
from app.schemas.llm_output import ProposalTextFields
from app.schemas.proposal import ProposalAssemblyRequest, SelectionContext, ShownCandidate


async def test_assemble_team_to_user_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_extract_structured(messages, response_model) -> ProposalTextFields:
        return ProposalTextFields(summary="핀테크 BE 결핍 팀입니다.", message="함께해요!")

    monkeypatch.setattr(proposal_module, "extract_structured", fake_extract_structured)

    request = ProposalAssemblyRequest(
        user_id=203,
        team_id=7,
        sender_id=7,
        receiver_id=203,
        synergy_score=0.83,
        candidate_summary="실무 3년차 백엔드 개발자, Spring Boot/Kafka 능숙",
        target_summary="핀테크 가계부 서비스, BE 1명 결핍",
    )

    result = await proposal_module.assemble_team_to_user_proposal(request)

    assert result.direction == MatchDirection.TEAM_TO_USER
    assert result.team_id == 7
    assert result.portfolio_role_fit_score is None
    assert result.summary == "핀테크 BE 결핍 팀입니다."


async def test_assemble_team_to_user_proposal_fires_judge_and_selection_log(
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
        team_id=7,
        sender_id=7,
        receiver_id=203,
        synergy_score=0.83,
        candidate_summary="실무 3년차 백엔드 개발자",
        target_summary="핀테크 가계부 서비스, BE 1명 결핍",
        selection_context=SelectionContext(
            idempotency_key="test-key-2",
            chooser_fields={"recruiting_roles": ["BE"], "contest_field": "FINTECH"},
            shown_candidates=[ShownCandidate(candidate_id=203, total_score=0.83, component_scores={})],
        ),
    )

    await proposal_module.assemble_team_to_user_proposal(request)

    assert fired == ["judge_and_log", "log_selection_event"]
