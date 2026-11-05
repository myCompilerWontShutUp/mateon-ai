"""운영 Supabase의 튜닝 설정 표에서 합성 데이터 출처의 활성 행을 끈다(삭제하지 않음).

2026-11-05 확인: `cluster_weight_config` 활성 행 63개, `event_cooccurrence` 활성 행 654개가 전부
합성 데모 데이터(source에 "synthetic")였고, 라이브 추천이 그 보정값을 읽고 있었다. 이 스크립트로
끈 뒤에는 실 데이터 배치가 새 버전을 쓰기 전까지 기본 WEIGHTS·CF 0점으로 동작한다.

행을 지우지 않으므로 되돌릴 수 있다 — 같은 source·version의 행을 is_active=true로 바꾸면 된다
(다만 라이브 서버는 합성 출처 행을 읽을 때도 무시하므로 다시 켜도 추천에는 반영되지 않는다).

사용 예:
    uv run python scripts/deactivate_synthetic_rows.py --dry-run
    uv run python scripts/deactivate_synthetic_rows.py
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.supabase_client.snapshots import is_synthetic_source  # noqa: E402
from app.supabase_client.client import get_supabase_client  # noqa: E402

TABLES = ("cluster_weight_config", "event_cooccurrence")
PAGE_SIZE = 1000


def _active_rows(client, table: str) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        res = (
            client.table(table)
            .select("id,source,version")
            .eq("is_active", True)
            .order("id")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )
        rows.extend(res.data)
        if len(res.data) < PAGE_SIZE:
            return rows
        start += PAGE_SIZE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="끌 행만 보여주고 바꾸지 않음")
    args = parser.parse_args()

    client = get_supabase_client()
    for table in TABLES:
        rows = _active_rows(client, table)
        synthetic = [row for row in rows if is_synthetic_source(row.get("source"))]
        by_source = Counter((row["source"], row.get("version")) for row in synthetic)
        print(f"[{table}] 활성 {len(rows)}행 중 합성 출처 {len(synthetic)}행")
        for (source, version), count in sorted(by_source.items()):
            print(f"  source={source} version={version}: {count}행")
        if not synthetic or args.dry_run:
            continue

        ids = [row["id"] for row in synthetic]
        for start in range(0, len(ids), 200):
            chunk = ids[start : start + 200]
            client.table(table).update({"is_active": False}).in_("id", chunk).execute()
        remaining = [r for r in _active_rows(client, table) if is_synthetic_source(r.get("source"))]
        print(f"  → {len(ids)}행 비활성화 완료, 남은 합성 활성 행 {len(remaining)}개")
        print(f"  되돌릴 id 목록(앞 5개): {ids[:5]} ... 총 {len(ids)}개")

    if args.dry_run:
        print("dry-run — 바꾸지 않았다.")


if __name__ == "__main__":
    main()
