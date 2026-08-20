import pytest

from app.scoring import cluster_weight_store


class _FakeResult:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class _FakeQuery:
    def __init__(self, sink: dict, table_state: list[dict]) -> None:
        self._sink = sink
        self._table_state = table_state
        self._filters: dict = {}
        self._select_cols: str | None = None
        self._update_payload: dict | None = None
        self._insert_payload: dict | None = None

    def select(self, cols: str) -> "_FakeQuery":
        self._select_cols = cols
        return self

    def eq(self, key: str, value) -> "_FakeQuery":
        self._filters[key] = value
        return self

    def update(self, payload: dict) -> "_FakeQuery":
        self._update_payload = payload
        return self

    def insert(self, payload: dict) -> "_FakeQuery":
        self._insert_payload = payload
        return self

    def execute(self) -> _FakeResult:
        if self._insert_payload is not None:
            row = {"id": f"row-{len(self._table_state)}", **self._insert_payload}
            self._table_state.append(row)
            self._sink.setdefault("inserts", []).append(self._insert_payload)
            return _FakeResult([row])

        if self._update_payload is not None:
            matched = [
                r for r in self._table_state if all(r.get(k) == v for k, v in self._filters.items())
            ]
            for row in matched:
                row.update(self._update_payload)
            self._sink.setdefault("updates", []).append((dict(self._filters), self._update_payload))
            return _FakeResult(matched)

        matched = [
            r for r in self._table_state if all(r.get(k) == v for k, v in self._filters.items())
        ]
        return _FakeResult(matched)


class _FakeClient:
    def __init__(self, sink: dict, table_state: list[dict]) -> None:
        self._sink = sink
        self._table_state = table_state

    def table(self, name: str) -> _FakeQuery:
        self._sink["table"] = name
        return _FakeQuery(self._sink, self._table_state)


def test_read_cluster_lifts_reconstructs_nested_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    sink: dict = {}
    table_state = [
        {"cluster_key": "BE:beginner", "component": "beginner_fit", "weight_value": 0.5, "is_active": True},
        {"cluster_key": "BE:beginner", "component": "role_match", "weight_value": 0.3, "is_active": True},
        {"cluster_key": "FE:advanced", "component": "similarity", "weight_value": 0.2, "is_active": True},
        {"cluster_key": "FE:advanced", "component": "similarity", "weight_value": 0.9, "is_active": False},
    ]
    monkeypatch.setattr(
        cluster_weight_store, "get_supabase_client", lambda: _FakeClient(sink, table_state)
    )

    lifts = cluster_weight_store.read_cluster_lifts()

    assert lifts == {
        "BE:beginner": {"beginner_fit": 0.5, "role_match": 0.3},
        "FE:advanced": {"similarity": 0.2},
    }


def test_read_cluster_lifts_returns_empty_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise():
        raise RuntimeError("network down")

    monkeypatch.setattr(cluster_weight_store, "get_supabase_client", _raise)

    assert cluster_weight_store.read_cluster_lifts() == {}


def test_write_cluster_lifts_inserts_version_1_when_no_existing_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink: dict = {}
    table_state: list[dict] = []
    monkeypatch.setattr(
        cluster_weight_store, "get_supabase_client", lambda: _FakeClient(sink, table_state)
    )

    cluster_weight_store.write_cluster_lifts({"BE:beginner": {"role_match": 0.4}}, source="test")

    inserted = sink["inserts"][0]
    assert inserted["cluster_key"] == "BE:beginner"
    assert inserted["component"] == "role_match"
    assert inserted["weight_type"] == "override"
    assert inserted["weight_value"] == 0.4
    assert inserted["version"] == 1
    assert inserted["is_active"] is True
    assert inserted["source"] == "test"


def test_write_cluster_lifts_deactivates_old_row_and_increments_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink: dict = {}
    table_state = [
        {
            "id": "existing-1",
            "cluster_key": "BE:beginner",
            "component": "role_match",
            "weight_value": 0.2,
            "version": 1,
            "is_active": True,
        }
    ]
    monkeypatch.setattr(
        cluster_weight_store, "get_supabase_client", lambda: _FakeClient(sink, table_state)
    )

    cluster_weight_store.write_cluster_lifts({"BE:beginner": {"role_match": 0.4}}, source="test")

    old_row = next(r for r in table_state if r["id"] == "existing-1")
    assert old_row["is_active"] is False  # 지워지지 않고 비활성화만 됨 — 롤백 가능

    new_row = sink["inserts"][0]
    assert new_row["version"] == 2
    assert new_row["is_active"] is True
