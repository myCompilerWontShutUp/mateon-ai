from fastapi import APIRouter, Depends

from app.api.internal_auth import require_internal_secret
from app.features.team_embedding.service import compute_team_embedding
from app.schemas.embedding import EmbeddingResult
from app.schemas.team_extraction import TeamEmbeddingRefreshRequest

router = APIRouter(tags=["team-embedding"], dependencies=[Depends(require_internal_secret)])


@router.post(
    "/internal/teams/embedding:refresh",
    summary="팀 임베딩 계산 (저장 없음, 팀 생성/수정 시 호출)",
)
async def refresh_team_embedding(request: TeamEmbeddingRefreshRequest) -> EmbeddingResult:
    return await compute_team_embedding(request)
