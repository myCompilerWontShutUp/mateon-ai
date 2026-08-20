import pytest

from app.features.quality import selection_log
from app.schemas.common import MatchDirection
from app.schemas.proposal import SelectionContext, ShownCandidate


class _FakeTable:
    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def upsert(self, row: dict, on_conflict: str) -> "_FakeTable":
        self._sink["row"] = row
        self._sink["on_conflict"] = on_conflict
        return self

    def execute(self) -> None:
        return None


class _FakeClient:
    def __init__(self, sink: dict) -> None:
        self._sink = sink

    def table(self, name: str) -> _FakeTable:
        self._sink["table"] = name
        return _FakeTable(self._sink)


async def test_log_selection_event_writes_expected_row(monkeypatch: pytest.MonkeyPatch) -> None:
    sink: dict = {}
    monkeypatch.setattr(selection_log, "get_supabase_client", lambda: _FakeClient(sink))

    selection_context = SelectionContext(
        idempotency_key="abc-123",
        chooser_fields={"desired_roles": ["BE"], "experience_level": "beginner"},
        shown_candidates=[
            ShownCandidate(candidate_id=17, total_score=0.91, component_scores={"similarity": 0.8})
        ],
    )

    await selection_log.log_selection_event(MatchDirection.USER_TO_TEAM, selection_context, 17)

    assert sink["table"] == "cluster_selection_events"
    assert sink["on_conflict"] == "idempotency_key"
    row = sink["row"]
    assert row["direction"] == "USER_TO_TEAM"
    assert row["idempotency_key"] == "abc-123"
    assert row["chooser_cluster_key"] == "BE:beginner"
    assert row["selected_candidate_id"] == 17
    assert row["shown_candidates"] == [
        {"candidate_id": 17, "total_score": 0.91, "component_scores": {"similarity": 0.8}}
    ]


async def test_log_selection_event_swallows_write_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise() -> None:
        raise RuntimeError("network down")

    monkeypatch.setattr(selection_log, "get_supabase_client", _raise)

    selection_context = SelectionContext(
        idempotency_key="abc-123", chooser_fields={}, shown_candidates=[]
    )

    # 예외가 밖으로 전파되면 안 된다 — fire-and-forget 계약.
    await selection_log.log_selection_event(MatchDirection.TEAM_TO_USER, selection_context, 1)
