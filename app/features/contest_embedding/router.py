from fastapi import APIRouter, Depends

from app.api.internal_auth import require_internal_secret
from app.features.contest_embedding.service import compute_contest_embedding
from app.schemas.contest_embedding import ContestEmbeddingRefreshRequest, ContestEmbeddingResult

router = APIRouter(tags=["contest-embedding"], dependencies=[Depends(require_internal_secret)])


@router.post(
    "/internal/contests/embedding:refresh",
    summary="공모전 임베딩 계산 (저장 없음, 공모전 등록/수정 시 호출)",
)
async def refresh_contest_embedding(request: ContestEmbeddingRefreshRequest) -> ContestEmbeddingResult:
    return await compute_contest_embedding(request)
