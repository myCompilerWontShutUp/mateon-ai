"""저장소 계층 테스트용 Supabase(PostgREST) 가짜 클라이언트.

실제 코드가 쓰는 체인(select/insert/update/eq/in_/order/range/limit/execute)만 흉내 낸다. 표는
행 dict의 리스트이고, 삽입하면 id가 붙는다. 호출 기록(calls)으로 "부르지 않았다"도 검사할 수 있다.

실제 서버처럼 동작해야 잡히는 버그가 있어 다음도 흉내 낸다.
- select("a,b")는 그 열만 돌려준다(읽는 쪽이 필요한 열을 빠뜨리면 테스트가 잡는다).
- max_rows: PostgREST의 응답 행 상한. range/limit 뒤에도 이 수를 넘겨 돌려주지 않는다.
- unique_active: {표: (열, ...)} — 활성 행끼리 이 열 조합이 겹치면 실패한다(운영 표의 부분 유니크 인덱스).
- fail_on: (작업, n) — 그 작업(insert/update/select)의 n번째 호출에서 실패한다(중간 실패 재현).
"""


class FakeResult:
    def __init__(self, data: list[dict]) -> None:
        self.data = data


class FakeQuery:
    def __init__(self, db: "FakeSupabase", table: str) -> None:
        self._db = db
        self._table = table
        self._op = "select"
        self._columns: list[str] | None = None
        self._payload = None
        self._filters: list = []
        self._order: tuple[str, bool] | None = None
        self._range: tuple[int, int] | None = None
        self._limit: int | None = None

    def select(self, columns: str) -> "FakeQuery":
        self._op = "select"
        names = [c.strip() for c in columns.split(",")]
        self._columns = None if names == ["*"] else names
        return self

    def insert(self, payload) -> "FakeQuery":
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict) -> "FakeQuery":
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, key: str, value) -> "FakeQuery":
        self._filters.append(lambda row: row.get(key) == value)
        return self

    def in_(self, key: str, values) -> "FakeQuery":
        allowed = set(values)
        self._filters.append(lambda row: row.get(key) in allowed)
        return self

    def order(self, column: str, desc: bool = False) -> "FakeQuery":
        self._order = (column, desc)
        return self

    def range(self, start: int, end: int) -> "FakeQuery":
        self._range = (start, end)
        return self

    def limit(self, count: int) -> "FakeQuery":
        self._limit = count
        return self

    def execute(self) -> FakeResult:
        db = self._db
        rows = db.tables.setdefault(self._table, [])
        db.calls.append((self._table, self._op))
        db.op_counts[self._op] = db.op_counts.get(self._op, 0) + 1
        if db.fail_on == (self._op, db.op_counts[self._op]):
            raise RuntimeError(f"injected failure on {self._op} #{db.op_counts[self._op]}")

        if self._op == "insert":
            payloads = self._payload if isinstance(self._payload, list) else [self._payload]
            inserted = []
            for payload in payloads:
                row = {"id": f"{self._table}-{len(rows) + 1:05d}", **payload}
                rows.append(row)
                inserted.append(dict(row))
            db.check_unique_active(self._table)
            return FakeResult(inserted)

        matched = [row for row in rows if all(check(row) for check in self._filters)]
        if self._op == "update":
            for row in matched:
                row.update(self._payload)
            db.check_unique_active(self._table)
            return FakeResult([dict(row) for row in matched])

        if self._order is not None:
            column, desc = self._order
            matched = sorted(matched, key=lambda row: row.get(column), reverse=desc)
        if self._range is not None:
            matched = matched[self._range[0] : self._range[1] + 1]
        if self._limit is not None:
            matched = matched[: self._limit]
        if db.max_rows is not None:
            matched = matched[: db.max_rows]
        if self._columns is not None:
            return FakeResult([{c: row[c] for c in self._columns if c in row} for row in matched])
        return FakeResult([dict(row) for row in matched])


class FakeSupabase:
    def __init__(
        self,
        tables: dict[str, list[dict]] | None = None,
        *,
        max_rows: int | None = None,
        unique_active: dict[str, tuple[str, ...]] | None = None,
        fail_on: tuple[str, int] | None = None,
    ) -> None:
        self.tables: dict[str, list[dict]] = tables if tables is not None else {}
        self.calls: list[tuple[str, str]] = []
        self.op_counts: dict[str, int] = {}
        self.max_rows = max_rows
        self.unique_active = unique_active or {}
        self.fail_on = fail_on
        # 실제 표처럼 모든 행에 id가 있게 한다(id 순 페이지 조회를 흉내 내기 위함).
        for name, rows in self.tables.items():
            for index, row in enumerate(rows, start=1):
                row.setdefault("id", f"{name}-{index:05d}")

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)

    def check_unique_active(self, table: str) -> None:
        columns = self.unique_active.get(table)
        if columns is None:
            return
        seen: set[tuple] = set()
        for row in self.tables.get(table, []):
            if not row.get("is_active"):
                continue
            key = tuple(row.get(c) for c in columns)
            if key in seen:
                raise RuntimeError(f"duplicate active row in {table}: {key}")
            seen.add(key)
