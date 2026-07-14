from fastapi import APIRouter

from app.features.user_to_team.intent import compute_user_intent
from app.features.user_to_team.proposal import assemble_user_to_team_proposal
from app.features.user_to_team.recommend import recommend_teams
from app.schemas.proposal import ProposalAssemblyRequest, ProposalSchema
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.schemas.user_intent import UserIntentExtractionRequest, UserIntentExtractionResult

router = APIRouter()


@router.post("/intents/extract")
async def extract_intent(request: UserIntentExtractionRequest) -> UserIntentExtractionResult:
    return await compute_user_intent(request)


@router.post("/recommendations/user-to-team")
async def recommend_user_to_team(request: RecommendationRequest) -> RecommendationResponse:
    return recommend_teams(request)


@router.post("/proposals/user-to-team")
async def create_user_to_team_proposal(request: ProposalAssemblyRequest) -> ProposalSchema:
    return await assemble_user_to_team_proposal(request)
