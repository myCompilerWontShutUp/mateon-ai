from fastapi import APIRouter, Depends

from app.api.internal_auth import require_internal_secret
from app.features.team_to_user.proposal import assemble_team_to_user_proposal
from app.features.team_to_user.recommend import recommend_users
from app.schemas.proposal import ProposalAssemblyRequest, ProposalSchema
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse

router = APIRouter(tags=["team-to-user"], dependencies=[Depends(require_internal_secret)])


@router.post("/recommendations/team-to-user", summary="역제안 추천 — 팀 결핍 기준 유저 Top N")
async def recommend_team_to_user(request: RecommendationRequest) -> RecommendationResponse:
    return recommend_users(request)


@router.post("/proposals/team-to-user", summary="역제안 최종 조립 (proposal_id는 백엔드가 채번)")
async def create_team_to_user_proposal(request: ProposalAssemblyRequest) -> ProposalSchema:
    return await assemble_team_to_user_proposal(request)
