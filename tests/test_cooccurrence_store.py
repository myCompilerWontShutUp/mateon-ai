import pytest

from app.scoring import cooccurrence_store
from app.supabase_client import snapshots
from app.supabase_client.client import LIVE_READ_FAILURE_BACKOFF_SECONDS
from tests.supabase_fake import FakeSupabase

TABLE = "event_cooccurrence"


@pytest.fixture(autouse=True)
def _fresh_backoff():
    cooccurrence_store.reset_backoff()
    yield
    cooccurrence_store.reset_backoff()


def _row(event_id, related_id, similarity, *, active=True, source="offline_batch_real_2026-11-05", version=1):
    return {
        "event_id": event_id,
        "related_event_id": related_id,
        "similarity": similarity,
        "is_active": active,
        "source": source,
        "version": version,
    }


def _use(monkeypatch: pytest.MonkeyPatch, db: FakeSupabase) -> FakeSupabase:
    monkeypatch.setattr(cooccurrence_store, "get_supabase_client", lambda: db)
    monkeypatch.setattr(cooccurrence_store, "get_supabase_read_client", lambda: db)
    return db


def test_reads_only_the_target_events_neighbors(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(
        monkeypatch,
        FakeSupabase(
            {
                TABLE: [
                    _row(300, 100, 0.8),
                    _row(100, 300, 0.8),
                    _row(500, 600, 0.4),
                    _row(300, 700, 0.9, active=False),
                ]
            }
        ),
    )

    assert cooccurrence_store.read_cooccurrence(["300"]) == {300: {100: 0.8}}


def test_related_ids_limit_the_read_to_those_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    """USER_TO_TEAM은 사용자가 본 공모전과의 쌍만 쓴다 — 나머지 이웃은 읽지 않는다."""
    _use(monkeypatch, FakeSupabase({TABLE: [_row(300, 100, 0.8), _row(300, 200, 0.6), _row(300, 400, 0.5)]}))

    assert cooccurrence_store.read_cooccurrence([300], related_event_ids=["100", 200]) == {
        300: {100: 0.8, 200: 0.6}
    }


def test_ignores_synthetic_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(
        monkeypatch,
        FakeSupabase({TABLE: [_row(300, 100, 0.8, source="offline_batch_synthetic_demo_20260901")]}),
    )

    assert cooccurrence_store.read_cooccurrence([300]) == {}


def test_no_ids_means_no_supabase_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def _record():
        calls.append(1)
        return FakeSupabase()

    monkeypatch.setattr(cooccurrence_store, "get_supabase_read_client", _record)

    assert cooccurrence_store.read_cooccurrence([]) == {}
    assert cooccurrence_store.read_cooccurrence([None, "not-a-number"]) == {}
    assert cooccurrence_store.read_cooccurrence([300], related_event_ids=[]) == {}
    assert calls == []


def test_read_pages_and_chunks_past_the_server_row_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(snapshots, "PAGE_SIZE", 2)
    monkeypatch.setattr(cooccurrence_store, "ID_CHUNK", 1)
    rows = [_row(1, related, 0.1) for related in range(10, 15)] + [_row(2, 99, 0.5)]
    _use(monkeypatch, FakeSupabase({TABLE: rows}, max_rows=2))

    result = cooccurrence_store.read_cooccurrence([1, 2])

    assert len(result[1]) == 5
    assert result[2] == {99: 0.5}


def test_read_failure_backs_off(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1_000.0]
    monkeypatch.setattr(cooccurrence_store, "_monotonic", lambda: now[0])
    attempts: list[int] = []

    def _raise():
        attempts.append(1)
        raise RuntimeError("network down")

    monkeypatch.setattr(cooccurrence_store, "get_supabase_read_client", _raise)

    assert cooccurrence_store.read_cooccurrence([300]) == {}
    now[0] += LIVE_READ_FAILURE_BACKOFF_SECONDS - 1
    assert cooccurrence_store.read_cooccurrence([300]) == {}
    assert attempts == [1]

    now[0] += 2
    assert cooccurrence_store.read_cooccurrence([300]) == {}
    assert attempts == [1, 1]


def test_write_records_a_snapshot_version(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _use(monkeypatch, FakeSupabase({TABLE: [{**_row(1, 2, 0.3, version=4), "id": "old"}]}))

    version = cooccurrence_store.write_cooccurrence({300: {100: 0.8}, 100: {300: 0.8}}, source="offline_batch_real_x")

    assert version == 5
    rows = db.tables[TABLE]
    assert next(r for r in rows if r["id"] == "old")["is_active"] is False
    active = sorted((r["event_id"], r["related_event_id"], r["version"]) for r in rows if r["is_active"])
    assert active == [(100, 300, 5), (300, 100, 5)]


def test_failed_insert_leaves_the_previous_version_active(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _use(
        monkeypatch,
        FakeSupabase({TABLE: [{**_row(1, 2, 0.3, version=4), "id": "old"}]}, fail_on=("insert", 1)),
    )

    with pytest.raises(RuntimeError):
        cooccurrence_store.write_cooccurrence({300: {100: 0.8}}, source="offline_batch_real_x")

    assert [r["id"] for r in db.tables[TABLE] if r["is_active"]] == ["old"]


def test_write_refuses_synthetic_and_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _use(monkeypatch, FakeSupabase())

    with pytest.raises(ValueError):
        cooccurrence_store.write_cooccurrence({1: {2: 0.5}}, source="offline_batch_synthetic_demo")
    with pytest.raises(ValueError):
        cooccurrence_store.write_cooccurrence({}, source="offline_batch_real_x")
    assert db.calls == []


def test_activate_version_and_deactivate_all(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _use(
        monkeypatch,
        FakeSupabase(
            {
                TABLE: [
                    {**_row(1, 2, 0.3, version=1, active=False), "id": "v1"},
                    {**_row(1, 2, 0.6, version=2), "id": "v2"},
                ]
            }
        ),
    )

    cooccurrence_store.activate_version(1)
    assert {r["id"]: r["is_active"] for r in db.tables[TABLE]} == {"v1": True, "v2": False}
    with pytest.raises(ValueError):
        cooccurrence_store.activate_version(99)

    assert cooccurrence_store.deactivate_all() == 1
    assert not any(r["is_active"] for r in db.tables[TABLE])
