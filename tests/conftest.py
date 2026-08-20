from collections.abc import Coroutine
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.features.recommendation import reason as reason_module
from app.features.team_to_user import proposal as team_to_user_proposal_module
from app.features.team_to_user import recommend as team_to_user_recommend_module
from app.features.user_to_team import proposal as user_to_team_proposal_module
from app.features.user_to_team import recommend as user_to_team_recommend_module
from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _no_background_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """judge_and_log/log_selection_event 같은 fire-and-forget 백그라운드 작업이 단위 테스트
    중 실제 OpenAI/Supabase 호출을 만들지 않도록 기본적으로 무력화한다. 이 배선 자체를 검증하는
    테스트는 로컬에서 fire_and_forget을 다시 monkeypatch해서 override할 수 있다."""

    def _noop(coro: Coroutine[Any, Any, Any]) -> None:
        coro.close()  # "coroutine was never awaited" 경고 방지

    monkeypatch.setattr(user_to_team_proposal_module, "fire_and_forget", _noop)
    monkeypatch.setattr(team_to_user_proposal_module, "fire_and_forget", _noop)
    monkeypatch.setattr(reason_module, "fire_and_forget", _noop)


@pytest.fixture(autouse=True)
def _no_cluster_weight_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """recommend_teams/recommend_users가 1번 항목(클러스터 가중치 보정)을 위해 읽는
    read_cluster_lifts()를 기본적으로 빈 dict로 고정한다 — 단위 테스트가 실제 Supabase를
    조회하지 않고, adjust_weights({})가 base WEIGHTS를 그대로 돌려주는 결정론적 동작만
    검증하게 하기 위함. 보정 자체를 검증하는 테스트는 로컬에서 다시 monkeypatch한다."""

    def _empty_lifts() -> dict:
        return {}

    monkeypatch.setattr(user_to_team_recommend_module, "read_cluster_lifts", _empty_lifts)
    monkeypatch.setattr(team_to_user_recommend_module, "read_cluster_lifts", _empty_lifts)
