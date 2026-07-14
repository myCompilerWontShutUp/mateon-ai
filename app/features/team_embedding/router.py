from fastapi import APIRouter, Depends

from app.api.internal_auth import require_internal_secret
from app.features.team_embedding.service import compute_team_embedding
from app.schemas.embedding import EmbeddingResult
from app.schemas.team_extraction import TeamEmbeddingRefreshRequest

router = APIRouter(dependencies=[Depends(require_internal_secret)])


@router.post("/internal/teams/embedding:refresh")
async def refresh_team_embedding(request: TeamEmbeddingRefreshRequest) -> EmbeddingResult:
    return await compute_team_embedding(request)
