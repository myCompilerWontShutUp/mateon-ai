from fastapi import APIRouter, Depends

from app.api.internal_auth import require_internal_secret
from app.features.team_to_user.proposal import assemble_team_to_user_proposal
from app.features.team_to_user.recommend import recommend_users
from app.schemas.proposal import ProposalAssemblyRequest, ProposalSchema
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse

router = APIRouter(dependencies=[Depends(require_internal_secret)])


@router.post("/recommendations/team-to-user")
async def recommend_team_to_user(request: RecommendationRequest) -> RecommendationResponse:
    return recommend_users(request)


@router.post("/proposals/team-to-user")
async def create_team_to_user_proposal(request: ProposalAssemblyRequest) -> ProposalSchema:
    return await assemble_team_to_user_proposal(request)
