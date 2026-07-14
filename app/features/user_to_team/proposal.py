from app.openai_client.extraction import extract_structured
from app.schemas.common import MatchDirection
from app.schemas.llm_output import ProposalTextFields
from app.schemas.proposal import ProposalAssemblyRequest, ProposalSchema

_SYSTEM_PROMPT = (
    "너는 사용자가 팀에 보낼 제안의 요약과 지원 메시지를 작성하는 도우미다. summary는 한 문장, "
    "message는 팀에 보내는 지원 동기 메시지로 두세 문장을 작성해라. ID나 점수는 절대 언급하지 "
    "마라."
)


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
