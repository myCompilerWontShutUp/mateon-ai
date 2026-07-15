from app.core.prompts import load_prompt
from app.openai_client.extraction import extract_structured
from app.schemas.common import MatchDirection
from app.schemas.llm_output import ProposalTextFields
from app.schemas.proposal import ProposalAssemblyRequest, ProposalSchema

_SYSTEM_PROMPT = load_prompt("team_to_user_proposal")


async def assemble_team_to_user_proposal(request: ProposalAssemblyRequest) -> ProposalSchema:
    prompt = f"팀 요약: {request.target_summary}\n스카우트 대상 요약: {request.candidate_summary}"
    text_fields = await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_model=ProposalTextFields,
    )

    return ProposalSchema(
        direction=MatchDirection.TEAM_TO_USER,
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
