from app.core.prompts import load_prompt
from app.openai_client.extraction import extract_structured
from app.schemas.common import MatchDirection
from app.schemas.llm_output import ProposalTextFields
from app.schemas.proposal import ProposalAssemblyRequest, ProposalSchema

_SYSTEM_PROMPT = load_prompt("user_to_team_proposal")


async def assemble_user_to_team_proposal(request: ProposalAssemblyRequest) -> ProposalSchema:
    prompt = f"지원자 요약: {request.candidate_summary}\n팀 요약: {request.target_summary}"
    text_fields = await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_model=ProposalTextFields,
    )

    return ProposalSchema(
        direction=MatchDirection.USER_TO_TEAM,
        user_id=request.user_id,
        team_id=request.team_id,
        contest_id=request.contest_id,
        sender_id=request.sender_id,
        receiver_id=request.receiver_id,
        intent_id=request.intent_id,
        synergy_score=request.synergy_score,
        portfolio_role_fit_score=None,
        summary=text_fields.summary,
        message=text_fields.message,
    )
