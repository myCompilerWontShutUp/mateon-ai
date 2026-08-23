import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.features.quality import router as router_module


def _payload() -> dict:
    return {
        "direction": "USER_TO_TEAM",
        "selected_candidate_id": 17,
        "selection_context": {
            "idempotency_key": "b3f1-test",
            "chooser_fields": {"desired_roles": ["BE"], "experience_level": "beginner"},
            "shown_candidates": [
                {
                    "candidate_id": 17,
                    "total_score": 0.91,
                    "component_scores": {
                        "similarity": 0.8,
                        "role_match": 1.0,
                        "deficit_fit": 1.0,
                        "beginner_fit": 0.5,
                        "activity_style_match": 1.0,
                    },
                }
            ],
        },
    }


async def test_selection_events_without_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/selection-events", json=_payload())
    assert response.status_code == 422  # missing required header


async def test_selection_events_with_wrong_secret_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/selection-events", json=_payload(), headers={"X-Internal-Secret": "wrong"}
    )
    assert response.status_code == 401


async def test_selection_events_with_correct_secret_succeeds(client: AsyncClient) -> None:
    secret = get_settings().internal_shared_secret
    response = await client.post(
        "/selection-events", json=_payload(), headers={"X-Internal-Secret": secret}
    )
    assert response.status_code == 200
    assert response.json() == {"accepted": True}


async def test_selection_events_fires_log_selection_event(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """fire-and-forget 배선 자체를 검증한다 — conftest의 autouse noop을 이 테스트에서만 override."""
    fired: list[str] = []

    def fake_fire_and_forget(coro) -> None:
        fired.append(coro.cr_code.co_name)
        coro.close()

    monkeypatch.setattr(router_module, "fire_and_forget", fake_fire_and_forget)

    secret = get_settings().internal_shared_secret
    response = await client.post(
        "/selection-events", json=_payload(), headers={"X-Internal-Secret": secret}
    )

    assert response.status_code == 200
    assert fired == ["log_selection_event"]
