from fastapi import APIRouter, Depends

from app.api.internal_auth import require_internal_secret
from app.features.recommendation.reason import generate_recommendation_reason
from app.schemas.recommendation import RecommendationReason, RecommendationReasonRequest

router = APIRouter(dependencies=[Depends(require_internal_secret)])


@router.post("/recommendations/reason")
async def recommend_reason(request: RecommendationReasonRequest) -> RecommendationReason:
    return await generate_recommendation_reason(request)
