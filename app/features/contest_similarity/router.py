from fastapi import APIRouter, Depends

from app.api.internal_auth import require_internal_secret
from app.features.contest_similarity.service import compute_contest_similarity
from app.schemas.contest_similarity import ContestSimilarityRequest, ContestSimilarityResponse

router = APIRouter(tags=["contest-similarity"], dependencies=[Depends(require_internal_secret)])


@router.post(
    "/contests/similarity-map",
    summary="쿼리 공모전 1건 중심의 유사도 방사형 배치 (순위 기반, 시각화용)",
)
async def get_contest_similarity_map(request: ContestSimilarityRequest) -> ContestSimilarityResponse:
    return await compute_contest_similarity(request)
