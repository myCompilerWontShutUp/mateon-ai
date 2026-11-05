"""운영 설정 표(`cluster_weight_config`, `event_cooccurrence`)의 공통 규칙.

두 표 모두 오프라인 배치가 "배치 하나 = 버전 하나"인 스냅샷으로 쓰고, 라이브 서버는 활성(is_active)
행만 읽는다. 이전 버전은 지우지 않으므로 활성 버전만 바꾸면 롤백된다. 합성 데이터 출처(source에
"synthetic")는 기록하지 않고, 읽을 때도 무시한다 — 2026-11-05 운영 표의 활성 행이 전부 합성 데모
데이터였고 라이브 추천이 그 값을 쓰고 있었다.
"""

from collections.abc import Callable

SYNTHETIC_SOURCE_MARKER = "synthetic"
# PostgREST의 max-rows(Supabase 기본 1,000)가 이 값 이상이라고 가정한다 — 이보다 짧은 페이지를 끝으로
# 본다. 프로젝트에서 max-rows를 더 낮추면 이 값도 같이 낮춰야 한다.
PAGE_SIZE = 1000
INSERT_BATCH = 500


def is_synthetic_source(source: str | None) -> bool:
    return SYNTHETIC_SOURCE_MARKER in (source or "").lower()


def fetch_pages(build_query: Callable[[int, int], object], page_size: int | None = None) -> list[dict]:
    """build_query(start, end)가 만든 조회를 페이지 단위로 끝까지 읽는다.

    조회는 id 순으로 정렬해 둬야 페이지 경계에서 행이 빠지거나 겹치지 않는다. page_size를 생략하면
    PAGE_SIZE를 쓴다(테스트가 모듈 값을 바꿔도 반영되게 호출 시점에 읽는다).
    """
    size = page_size or PAGE_SIZE
    rows: list[dict] = []
    start = 0
    while True:
        page = build_query(start, start + size - 1).execute().data
        rows.extend(page)
        if len(page) < size:
            return rows
        start += size


def write_snapshot(client, table: str, rows: list[dict]) -> int:
    """rows를 새 버전 하나로 기록하고 그 버전을 켠 뒤 버전 번호를 돌려준다.

    순서: 새 버전을 비활성으로 먼저 넣고 → 이전 활성 행을 전부 끄고 → 새 버전을 켠다. 도중에 실패해도
    "이전 버전이 그대로 켜진 상태"나 "아무 행도 켜지지 않은 상태" 중 하나가 남을 뿐, 두 버전이 섞여
    켜지지 않는다(아무것도 안 켜진 상태는 기본 가중치·CF 0점으로 동작한다).
    """
    if not rows:
        raise ValueError(f"{table}에 기록할 행이 없다")
    if any(is_synthetic_source(row.get("source")) for row in rows):
        raise ValueError(f"합성 데이터는 운영 {table}에 기록하지 않는다")

    latest = client.table(table).select("version").order("version", desc=True).limit(1).execute().data
    version = latest[0]["version"] + 1 if latest else 1
    stamped = [{**row, "version": version, "is_active": False} for row in rows]
    for start in range(0, len(stamped), INSERT_BATCH):
        client.table(table).insert(stamped[start : start + INSERT_BATCH]).execute()
    _switch_to(client, table, version)
    return version


def activate_version(client, table: str, version: int) -> None:
    """지정한 버전만 켜고 나머지는 끈다 — 재계산이 오히려 나빴을 때의 롤백용.

    배치 하나가 출처(source) 하나로 기록되므로 첫 행의 출처로 판단해, 합성 데이터 버전은 켜지 않는다
    (켜도 읽는 쪽이 무시하므로 "아무 보정도 없는 상태"를 롤백으로 착각하게 된다).
    """
    sample = client.table(table).select("source").eq("version", version).limit(1).execute().data
    if not sample:
        raise ValueError(f"{table}에 버전 {version}이 없다")
    if is_synthetic_source(sample[0].get("source")):
        raise ValueError(f"{table} 버전 {version}은 합성 데이터라 켜지 않는다")
    _switch_to(client, table, version)


def deactivate_all(client, table: str) -> int:
    """활성 행을 전부 끈다 — 새로 계산한 값이 없는데 옛 값을 내려야 할 때 쓴다. 끈 행 수를 돌려준다."""
    return len(client.table(table).update({"is_active": False}).eq("is_active", True).execute().data)


def _switch_to(client, table: str, version: int) -> None:
    client.table(table).update({"is_active": False}).eq("is_active", True).execute()
    client.table(table).update({"is_active": True}).eq("version", version).execute()
