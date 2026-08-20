from app.core.background import fire_and_forget
from app.core.prompts import load_prompt
from app.features.quality.judge import judge_and_log
from app.features.quality.selection_log import log_selection_event
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

    fire_and_forget(
        judge_and_log(
            "user_to_team_proposal",
            prompt,
            f"summary: {text_fields.summary}\nmessage: {text_fields.message}",
        )
    )
    if request.selection_context is not None:
        fire_and_forget(
            log_selection_event(MatchDirection.USER_TO_TEAM, request.selection_context, request.team_id)
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
