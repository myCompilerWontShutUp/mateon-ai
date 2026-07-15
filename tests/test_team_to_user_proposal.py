import pytest

from app.features.team_to_user import proposal as proposal_module
from app.schemas.common import MatchDirection
from app.schemas.llm_output import ProposalTextFields
from app.schemas.proposal import ProposalAssemblyRequest


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
        portfolio_role_fit_score=1.0,
        candidate_summary="실무 3년차 백엔드 개발자, Spring Boot/Kafka 능숙",
        target_summary="핀테크 가계부 서비스, BE 1명 결핍",
    )

    result = await proposal_module.assemble_team_to_user_proposal(request)

    assert result.direction == MatchDirection.TEAM_TO_USER
    assert result.team_id == 7
    assert result.portfolio_role_fit_score == 1.0
    assert result.summary == "핀테크 BE 결핍 팀입니다."
