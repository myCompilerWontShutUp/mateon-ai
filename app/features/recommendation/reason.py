from app.core.prompts import load_prompt
from app.openai_client.extraction import extract_structured
from app.schemas.llm_output import RecommendationReasonText
from app.schemas.recommendation import RecommendationReason, RecommendationReasonRequest

_SYSTEM_PROMPT = load_prompt("recommendation_reason")


async def generate_recommendation_reason(request: RecommendationReasonRequest) -> RecommendationReason:
    prompt = (
        f"후보 요약: {request.candidate_summary}\n"
        f"대상 요약: {request.target_summary}\n"
        f"점수 구성: {request.score_context}"
    )
    text = await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_model=RecommendationReasonText,
    )
    return RecommendationReason(reason=text.reason)
