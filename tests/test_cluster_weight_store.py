import pytest

from app.core.config import get_settings
from app.scoring import cluster_weight_store
from app.supabase_client import snapshots
from app.supabase_client.client import LIVE_READ_FAILURE_BACKOFF_SECONDS
from tests.supabase_fake import FakeSupabase

TABLE = "cluster_weight_config"
# 운영 표의 부분 유니크 인덱스(uq_cluster_weight_config_active)와 같은 제약.
UNIQUE_ACTIVE = {TABLE: ("cluster_key", "component")}


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def _fresh_cache():
    cluster_weight_store.clear_cache()
    yield
    cluster_weight_store.clear_cache()


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    clock = _Clock()
    monkeypatch.setattr(cluster_weight_store, "_monotonic", clock)
    # 개발자 .env의 CONFIG_CACHE_SECONDS와 무관하게 TTL을 고정한다.
    settings = get_settings().model_copy(update={"config_cache_seconds": 60})
    monkeypatch.setattr(cluster_weight_store, "get_settings", lambda: settings)
    return clock


def _use(monkeypatch: pytest.MonkeyPatch, db: FakeSupabase) -> FakeSupabase:
    monkeypatch.setattr(cluster_weight_store, "get_supabase_client", lambda: db)
    monkeypatch.setattr(cluster_weight_store, "get_supabase_read_client", lambda: db)
    return db


def _fail_reads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    attempts: list[int] = []

    def _raise():
        attempts.append(1)
        raise RuntimeError("network down")

    monkeypatch.setattr(cluster_weight_store, "get_supabase_read_client", _raise)
    return attempts


def _row(cluster_key, component, value, *, active=True, source="offline_batch_real_2026-11-05", version=1):
    return {
        "cluster_key": cluster_key,
        "component": component,
        "weight_value": value,
        "is_active": active,
        "source": source,
        "version": version,
    }


def test_read_cluster_lifts_reconstructs_nested_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(
        monkeypatch,
        FakeSupabase(
            {
                TABLE: [
                    _row("USER_TO_TEAM|BE:beginner", "beginner_fit", 0.5),
                    _row("USER_TO_TEAM|BE:beginner", "role_match", 0.3),
                    _row("USER_TO_TEAM|FE:advanced", "similarity", 0.2),
                    _row("USER_TO_TEAM|FE:advanced", "similarity", 0.9, active=False),
                ]
            }
        ),
    )

    assert cluster_weight_store.read_cluster_lifts() == {
        "USER_TO_TEAM|BE:beginner": {"beginner_fit": 0.5, "role_match": 0.3},
        "USER_TO_TEAM|FE:advanced": {"similarity": 0.2},
    }


def test_read_ignores_synthetic_rows_even_when_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """2026-11-05 운영 표의 활성 행이 전부 합성 데모였던 사고 — 라이브는 합성 출처를 쓰지 않는다."""
    _use(
        monkeypatch,
        FakeSupabase(
            {
                TABLE: [
                    _row("USER_TO_TEAM|BE:beginner", "role_match", 0.4, source="offline_batch_synthetic_demo_2026-08-20"),
                    _row("USER_TO_TEAM|FE:beginner", "role_match", 0.2),
                ]
            }
        ),
    )

    assert cluster_weight_store.read_cluster_lifts() == {"USER_TO_TEAM|FE:beginner": {"role_match": 0.2}}


def test_read_pages_past_the_server_row_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """PostgREST는 한 응답에 max-rows까지만 준다 — 페이지로 나눠 읽지 않으면 조용히 잘린다."""
    monkeypatch.setattr(snapshots, "PAGE_SIZE", 2)
    rows = [_row(f"USER_TO_TEAM|R{i}:beginner", "role_match", 0.1) for i in range(5)]
    _use(monkeypatch, FakeSupabase({TABLE: rows}, max_rows=2))

    assert len(cluster_weight_store.read_cluster_lifts()) == 5


def test_read_returns_empty_on_failure_without_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    _fail_reads(monkeypatch)

    assert cluster_weight_store.read_cluster_lifts() == {}


def test_cache_expires_and_failures_back_off(monkeypatch: pytest.MonkeyPatch, clock: _Clock) -> None:
    db = _use(monkeypatch, FakeSupabase({TABLE: [_row("USER_TO_TEAM|BE:beginner", "role_match", 0.3)]}))
    first = cluster_weight_store.read_cluster_lifts()
    calls_after_first = len(db.calls)

    # 캐시 시간 안에서는 다시 조회하지 않는다.
    clock.now += 59
    assert cluster_weight_store.read_cluster_lifts() == first
    assert len(db.calls) == calls_after_first

    # 만료되면 다시 읽어 새 값을 쓴다.
    db.tables[TABLE][0]["weight_value"] = 0.7
    clock.now += 2
    assert cluster_weight_store.read_cluster_lifts() == {"USER_TO_TEAM|BE:beginner": {"role_match": 0.7}}

    # 만료 뒤 조회가 실패하면 마지막으로 성공한 값을 쓰고, 한동안은 다시 시도하지 않는다.
    attempts = _fail_reads(monkeypatch)
    clock.now += 61
    assert cluster_weight_store.read_cluster_lifts() == {"USER_TO_TEAM|BE:beginner": {"role_match": 0.7}}
    clock.now += LIVE_READ_FAILURE_BACKOFF_SECONDS - 1
    assert cluster_weight_store.read_cluster_lifts() == {"USER_TO_TEAM|BE:beginner": {"role_match": 0.7}}
    assert attempts == [1]

    clock.now += 2
    cluster_weight_store.read_cluster_lifts()
    assert attempts == [1, 1]


def test_concurrent_refresh_does_not_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """다른 요청이 이미 Supabase를 읽는 중이면 기다리지 않고 직전 값(없으면 빈 dict)을 쓴다."""
    db = _use(monkeypatch, FakeSupabase({TABLE: [_row("USER_TO_TEAM|BE:beginner", "role_match", 0.3)]}))

    with cluster_weight_store._refresh_lock:
        assert cluster_weight_store.read_cluster_lifts() == {}
    assert db.calls == []


def test_write_records_a_snapshot_version_and_switches(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _use(
        monkeypatch,
        FakeSupabase(
            {
                TABLE: [
                    {**_row("USER_TO_TEAM|BE:beginner", "role_match", 0.2, version=2), "id": "old-1"},
                    # 새 배치에 없는 클러스터의 옛 lift도 함께 꺼져야 한다(살아남지 않게).
                    {**_row("USER_TO_TEAM|PM:advanced", "similarity", 0.1, version=2), "id": "old-2"},
                ]
            },
            unique_active=UNIQUE_ACTIVE,
        ),
    )

    version = cluster_weight_store.write_cluster_lifts(
        {"USER_TO_TEAM|BE:beginner": {"role_match": 0.4}}, source="offline_batch_real_2026-11-05"
    )

    assert version == 3
    rows = db.tables[TABLE]
    old = {r["id"]: r for r in rows if r["id"].startswith("old-")}
    assert old["old-1"]["is_active"] is False and old["old-2"]["is_active"] is False  # 지우지 않고 끔
    active = [r for r in rows if r["is_active"]]
    assert [(r["cluster_key"], r["component"], r["weight_value"], r["version"]) for r in active] == [
        ("USER_TO_TEAM|BE:beginner", "role_match", 0.4, 3)
    ]
    assert active[0]["weight_type"] == "override"
    # 새 버전을 꺼진 채로 넣은 뒤 → 이전 버전을 끄고 → 새 버전을 켠다.
    assert [op for _, op in db.calls] == ["select", "insert", "update", "update"]


def test_failed_insert_leaves_the_previous_version_active(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _use(
        monkeypatch,
        FakeSupabase(
            {TABLE: [{**_row("USER_TO_TEAM|BE:beginner", "role_match", 0.2, version=2), "id": "old"}]},
            unique_active=UNIQUE_ACTIVE,
            fail_on=("insert", 1),
        ),
    )

    with pytest.raises(RuntimeError):
        cluster_weight_store.write_cluster_lifts(
            {"USER_TO_TEAM|BE:beginner": {"role_match": 0.4}}, source="offline_batch_real_2026-11-05"
        )

    assert [r["id"] for r in db.tables[TABLE] if r["is_active"]] == ["old"]


def test_write_refuses_synthetic_sources_and_empty_lifts(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _use(monkeypatch, FakeSupabase())

    with pytest.raises(ValueError):
        cluster_weight_store.write_cluster_lifts({"k": {"role_match": 0.1}}, source="offline_batch_synthetic_x")
    with pytest.raises(ValueError):
        cluster_weight_store.write_cluster_lifts({}, source="offline_batch_real_x")
    assert db.calls == []


def test_activate_version_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _use(
        monkeypatch,
        FakeSupabase(
            {
                TABLE: [
                    {**_row("USER_TO_TEAM|BE:beginner", "role_match", 0.2, version=1, active=False), "id": "v1"},
                    {**_row("USER_TO_TEAM|BE:beginner", "role_match", 0.9, version=2), "id": "v2"},
                ]
            },
            unique_active=UNIQUE_ACTIVE,
        ),
    )

    cluster_weight_store.activate_version(1)

    state = {r["id"]: r["is_active"] for r in db.tables[TABLE]}
    assert state == {"v1": True, "v2": False}
    with pytest.raises(ValueError):
        cluster_weight_store.activate_version(99)


def test_activate_version_refuses_a_synthetic_version(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _use(
        monkeypatch,
        FakeSupabase(
            {
                TABLE: [
                    {**_row("k", "role_match", 0.2, version=1, active=False, source="offline_batch_synthetic_demo"), "id": "v1"},
                    {**_row("k", "role_match", 0.9, version=2), "id": "v2"},
                ]
            }
        ),
    )

    with pytest.raises(ValueError):
        cluster_weight_store.activate_version(1)
    assert {r["id"]: r["is_active"] for r in db.tables[TABLE]} == {"v1": False, "v2": True}


def test_deactivate_all_turns_every_active_row_off(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _use(
        monkeypatch,
        FakeSupabase({TABLE: [_row("a", "role_match", 0.2), _row("b", "role_match", 0.3, active=False)]}),
    )

    assert cluster_weight_store.deactivate_all() == 1
    assert not any(r["is_active"] for r in db.tables[TABLE])
