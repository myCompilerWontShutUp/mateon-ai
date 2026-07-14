import pytest

from app.features.user_to_team import proposal as proposal_module
from app.schemas.common import MatchDirection
from app.schemas.llm_output import ProposalTextFields
from app.schemas.proposal import ProposalAssemblyRequest


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
