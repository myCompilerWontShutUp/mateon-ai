import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.features.recommendation import router as recommendation_router_module
from app.features.user_to_team import router as router_module
from app.schemas.common import MatchDirection
from app.schemas.proposal import ProposalSchema
from app.schemas.recommendation import RecommendationItem, RecommendationReason, RecommendationResponse
from app.schemas.user_intent import UserIntentExtractionResult, UserIntentFields

_AUTH_HEADERS = {"X-Internal-Secret": get_settings().internal_shared_secret}


@pytest.fixture(autouse=True)
def _mock_services(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_compute_user_intent(request) -> UserIntentExtractionResult:
        return UserIntentExtractionResult(
            missing_fields=[], extracted=UserIntentFields(desired_roles=["BE"]), embedding_text="...",
            embedding_vector=[0.1] * 1536, assistant_message="너의 관심사는 백엔드구나! 이건 추천 팀이야.",
        )

    def fake_recommend_teams(request) -> RecommendationResponse:
        return RecommendationResponse(
            recommendations=[RecommendationItem(candidate_id=17, score=0.9, label="적합해요")]
        )

    async def fake_assemble_proposal(request) -> ProposalSchema:
        return ProposalSchema(
            direction=MatchDirection.USER_TO_TEAM,
            user_id=request.user_id,
            team_id=request.team_id,
            sender_id=request.sender_id,
            receiver_id=request.receiver_id,
            synergy_score=request.synergy_score,
            summary="요약",
            message="메시지",
        )

    async def fake_generate_reason(request) -> RecommendationReason:
        return RecommendationReason(reason="적합한 이유입니다.")

    monkeypatch.setattr(router_module, "compute_user_intent", fake_compute_user_intent)
    monkeypatch.setattr(router_module, "recommend_teams", fake_recommend_teams)
    monkeypatch.setattr(router_module, "assemble_user_to_team_proposal", fake_assemble_proposal)
    monkeypatch.setattr(recommendation_router_module, "generate_recommendation_reason", fake_generate_reason)


async def test_extract_intent_endpoint(client: AsyncClient) -> None:
    response = await client.post(
        "/intents/extract",
        json={"messages": [{"id": 1, "message": "백엔드를 해보고 싶습니다."}]},
        headers=_AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["missing_fields"] == []


async def test_extract_intent_endpoint_rejects_wrong_secret(client: AsyncClient) -> None:
    response = await client.post(
        "/intents/extract",
        json={"messages": [{"id": 1, "message": "..."}]},
        headers={"X-Internal-Secret": "wrong"},
    )
    assert response.status_code == 401


async def test_recommend_user_to_team_endpoint(client: AsyncClient) -> None:
    response = await client.post(
        "/recommendations/user-to-team",
        json={"query_embedding_vector": [0.1] * 1536, "candidates": []},
        headers=_AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["recommendations"][0]["candidate_id"] == 17


async def test_create_proposal_endpoint(client: AsyncClient) -> None:
    response = await client.post(
        "/proposals/user-to-team",
        json={
            "user_id": 203,
            "team_id": 17,
            "sender_id": 203,
            "receiver_id": 17,
            "synergy_score": 0.9,
            "candidate_summary": "...",
            "target_summary": "...",
        },
        headers=_AUTH_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["direction"] == "USER_TO_TEAM"
    assert "proposal_id" not in body


async def test_recommendation_reason_endpoint(client: AsyncClient) -> None:
    response = await client.post(
        "/recommendations/reason",
        json={"candidate_summary": "...", "target_summary": "..."},
        headers=_AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["reason"] == "적합한 이유입니다."


async def test_recommendation_reason_endpoint_requires_secret(client: AsyncClient) -> None:
    response = await client.post(
        "/recommendations/reason", json={"candidate_summary": "...", "target_summary": "..."}
    )
    assert response.status_code == 422  # missing required header
