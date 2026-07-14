from fastapi import APIRouter

from app.features.recommendation.reason import generate_recommendation_reason
from app.schemas.recommendation import RecommendationReason, RecommendationReasonRequest

router = APIRouter()


@router.post("/recommendations/reason")
async def recommend_reason(request: RecommendationReasonRequest) -> RecommendationReason:
    return await generate_recommendation_reason(request)
