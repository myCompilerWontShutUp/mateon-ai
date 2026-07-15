from app.openai_client.extraction import extract_structured
from app.schemas.common import MatchDirection
from app.schemas.llm_output import ProposalTextFields
from app.schemas.proposal import ProposalAssemblyRequest, ProposalSchema

_SYSTEM_PROMPT = (
    "너는 팀장이 사용자에게 보낼 스카우트 제안의 팀 소개 요약과 스카우트 메시지를 작성하는 "
    "도우미다. summary는 한 문장으로 팀을 소개하고, message는 사용자에게 보내는 스카우트 "
    "메시지로 두세 문장을 작성해라. 사용자에 대한 절대적 평가(훌륭하다/부족하다 등)는 하지 "
    "말고, 이 팀의 이 역할에 왜 적합한지만 언급해라. ID나 점수는 절대 언급하지 마라."
)


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
        portfolio_role_fit_score=request.portfolio_role_fit_score,
        summary=text_fields.summary,
        message=text_fields.message,
    )
