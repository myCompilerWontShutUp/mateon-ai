from fastapi import APIRouter, Depends

from app.api.internal_auth import require_internal_secret
from app.features.user_to_team.intent import compute_user_intent
from app.features.user_to_team.proposal import assemble_user_to_team_proposal
from app.features.user_to_team.recommend import recommend_teams
from app.schemas.proposal import ProposalAssemblyRequest, ProposalSchema
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.schemas.user_intent import UserIntentExtractionRequest, UserIntentExtractionResult

router = APIRouter(tags=["user-to-team"], dependencies=[Depends(require_internal_secret)])


@router.post("/intents/extract", summary="사용자 매칭 의도 추출 (재질문 시 stateless 재호출)")
async def extract_intent(request: UserIntentExtractionRequest) -> UserIntentExtractionResult:
    return await compute_user_intent(request)


@router.post("/recommendations/user-to-team", summary="제안 추천 — 유저 intent 기준 팀 Top 10")
async def recommend_user_to_team(request: RecommendationRequest) -> RecommendationResponse:
    return recommend_teams(request)


@router.post("/proposals/user-to-team", summary="제안 최종 조립 (proposal_id는 백엔드가 채번)")
async def create_user_to_team_proposal(request: ProposalAssemblyRequest) -> ProposalSchema:
    return await assemble_user_to_team_proposal(request)
