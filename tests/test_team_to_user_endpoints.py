import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.features.team_to_user import router as router_module
from app.schemas.common import MatchDirection
from app.schemas.proposal import ProposalSchema
from app.schemas.recommendation import RecommendationItem, RecommendationResponse

_AUTH_HEADERS = {"X-Internal-Secret": get_settings().internal_shared_secret}


@pytest.fixture(autouse=True)
def _mock_services(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_recommend_users(request) -> RecommendationResponse:
        return RecommendationResponse(
            recommendations=[RecommendationItem(candidate_id=203, score=0.9, label="적합해요")]
        )

    async def fake_assemble_proposal(request) -> ProposalSchema:
        return ProposalSchema(
            direction=MatchDirection.TEAM_TO_USER,
            user_id=request.user_id,
            team_id=request.team_id,
            sender_id=request.sender_id,
            receiver_id=request.receiver_id,
            synergy_score=request.synergy_score,
            portfolio_role_fit_score=request.portfolio_role_fit_score,
            summary="요약",
            message="스카우트 메시지",
        )

    monkeypatch.setattr(router_module, "recommend_users", fake_recommend_users)
    monkeypatch.setattr(router_module, "assemble_team_to_user_proposal", fake_assemble_proposal)


async def test_recommend_team_to_user_endpoint(client: AsyncClient) -> None:
    response = await client.post(
        "/recommendations/team-to-user",
        json={"query_embedding_vector": [0.1] * 1536, "candidates": []},
        headers=_AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["recommendations"][0]["candidate_id"] == 203


async def test_recommend_team_to_user_requires_secret(client: AsyncClient) -> None:
    response = await client.post(
        "/recommendations/team-to-user",
        json={"query_embedding_vector": [0.1] * 1536, "candidates": []},
    )
    assert response.status_code == 422


async def test_create_team_to_user_proposal_endpoint(client: AsyncClient) -> None:
    response = await client.post(
        "/proposals/team-to-user",
        json={
            "user_id": 203,
            "team_id": 7,
            "sender_id": 7,
            "receiver_id": 203,
            "synergy_score": 0.83,
            "portfolio_role_fit_score": 1.0,
            "candidate_summary": "...",
            "target_summary": "...",
        },
        headers=_AUTH_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["direction"] == "TEAM_TO_USER"
    assert body["portfolio_role_fit_score"] == 1.0
    assert "proposal_id" not in body
