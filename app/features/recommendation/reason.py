from app.openai_client.extraction import extract_structured
from app.schemas.llm_output import RecommendationReasonText
from app.schemas.recommendation import RecommendationReason, RecommendationReasonRequest

_SYSTEM_PROMPT = (
    "너는 매칭 추천 이유를 한두 문장으로 설명하는 도우미다. 사람에 대한 절대적 평가(훌륭하다/"
    "부족하다 등)를 하지 말고, 두 대상이 왜 서로 적합한지, 즉 '이 팀/역할에 대한 적합도' "
    "관점으로만 설명해라."
)


async def generate_recommendation_reason(request: RecommendationReasonRequest) -> RecommendationReason:
    prompt = (
        f"후보 요약: {request.candidate_summary}\n"
        f"대상 요약: {request.target_summary}\n"
        f"점수 구성: {request.score_breakdown}"
    )
    text = await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_model=RecommendationReasonText,
    )
    return RecommendationReason(reason=text.reason)
