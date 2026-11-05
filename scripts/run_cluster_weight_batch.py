"""1번 항목(오프라인 클러스터 가중치 재계산 배치) — CLAUDE.md "## 모니터링·데이터 기반 가중치
보정" 참고. AI 서버 프로세스 안에서 돌지 않고, 사람이 앱 업데이트 주기(1주~6개월)에 맞춰
로컬에서 수동 실행한다.

**실제 선택 이벤트(`cluster_selection_events`)만 쓴다.** 이전에는 실 이벤트가 없으면 합성 데이터로
자동 대체해 운영 표에 썼고, 그 값이 라이브 추천을 보정하고 있었다(2026-11-05 발견·정리,
`scripts/deactivate_synthetic_rows.py`). 합성 데이터로 계산 과정만 보고 싶으면 `--synthetic-demo`를
쓴다 — 결과를 출력만 하고 운영 표에는 절대 쓰지 않는다.

- 클러스터당 이벤트가 `--min-events`(기본 20)보다 적으면 보정하지 않는다. 몇 건짜리 lift는 잡음이다.
- 한 번 실행 = 한 버전(스냅샷)이다. 새 배치에 없는 클러스터의 옛 lift는 함께 꺼진다.
- 계산 결과가 비면 현재 활성 버전을 그대로 둔다. 옛 보정값을 내리려면 `--deactivate-all`을 쓴다.
- 키에는 방향을 붙인다(`app/scoring/cluster.py`의 `lift_key`).

사용 예(모드 플래그는 하나만 쓸 수 있다):
    uv run python scripts/run_cluster_weight_batch.py --dry-run          # 계산만, 기록 안 함
    uv run python scripts/run_cluster_weight_batch.py                    # 계산 후 새 버전 기록
    uv run python scripts/run_cluster_weight_batch.py --activate-version 3   # 버전 3으로 롤백
    uv run python scripts/run_cluster_weight_batch.py --deactivate-all   # 보정 끄기(기본 WEIGHTS)
    uv run python scripts/run_cluster_weight_batch.py --synthetic-demo   # 합성 데이터로 시연(출력만)
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 기본 cp949가 em dash(—) 등을 못 찍음
sys.stderr.reconfigure(encoding="utf-8")  # argparse 오류 메시지도 같은 이유

from app.scoring.cluster import lift_key  # noqa: E402
from app.scoring.cluster_weight_store import activate_version, deactivate_all, write_cluster_lifts  # noqa: E402
from app.scoring.cluster_weights import compute_weight_lifts  # noqa: E402
from app.supabase_client.client import get_supabase_client  # noqa: E402
from app.supabase_client.snapshots import fetch_pages  # noqa: E402

SYNTHETIC_EVENTS_PATH = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_synthetic_selections.json"
)
# cf_affinity도 포함한다 — 이 가중치(초기 0.05)도 실 데이터로 조정된다는 전제로 넣은 것이라서다.
COMPONENTS = [
    "similarity",
    "role_match",
    "deficit_fit",
    "beginner_fit",
    "activity_style_match",
    "cf_affinity",
]
DEFAULT_MIN_EVENTS = 20


def _load_real_events() -> list[dict]:
    client = get_supabase_client()
    # id(uuid)는 유일해서 페이지 경계가 흔들리지 않는다(created_at은 같은 값이 있을 수 있다).
    rows = fetch_pages(
        lambda start, end: client.table("cluster_selection_events")
        .select("direction,chooser_cluster_key,selected_candidate_id,shown_candidates")
        .order("id")
        .range(start, end)
    )
    return [
        {
            "chooser_cluster_key": lift_key(row["direction"], row["chooser_cluster_key"]),
            "selected_candidate_id": row["selected_candidate_id"],
            "shown_candidates": row["shown_candidates"],
        }
        for row in rows
    ]


def _print_lifts(lifts: dict[str, dict[str, float]]) -> None:
    print(f"{len(lifts)}개 클러스터에서 유의미한 lift 발견")
    for cluster_key, cluster_lifts in sorted(lifts.items()):
        rounded = {name: round(value, 4) for name, value in cluster_lifts.items()}
        print(f"  {cluster_key}: {rounded}")


def main() -> None:
    parser = argparse.ArgumentParser()
    # 운영 표를 바꾸는 플래그와 "기록하지 않는" 플래그가 섞이면 의도와 다르게 운영 표가 바뀐다
    # (--activate-version 3 --dry-run이 실제 롤백을 하던 문제) — 모드는 하나만 고르게 한다.
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="계산 결과만 출력하고 기록하지 않음")
    mode.add_argument("--activate-version", type=int, help="이 버전만 켜고 나머지는 끈다(롤백)")
    mode.add_argument("--deactivate-all", action="store_true", help="활성 lift를 전부 끈다(기본 WEIGHTS로 복귀)")
    mode.add_argument(
        "--synthetic-demo",
        action="store_true",
        help="합성 이벤트로 계산 과정만 시연(출력만, 운영 표에 기록하지 않음)",
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=DEFAULT_MIN_EVENTS,
        help=f"클러스터당 최소 이벤트 수(기본 {DEFAULT_MIN_EVENTS})",
    )
    args = parser.parse_args()

    if args.activate_version is not None:
        activate_version(args.activate_version)
        print(f"cluster_weight_config 버전 {args.activate_version}로 전환 완료")
        return
    if args.deactivate_all:
        print(f"cluster_weight_config 활성 행 {deactivate_all()}개를 껐다 — 기본 WEIGHTS로 동작한다.")
        return

    if args.synthetic_demo:
        events = json.loads(SYNTHETIC_EVENTS_PATH.read_text(encoding="utf-8"))
        print(f"합성 이벤트 {len(events)}건으로 시연 — 운영 표에는 기록하지 않는다.")
        _print_lifts(compute_weight_lifts(events, components=COMPONENTS, min_events=2))
        return

    events = _load_real_events()
    print(f"실 cluster_selection_events {len(events)}건 (클러스터당 최소 {args.min_events}건)")
    lifts = compute_weight_lifts(events, components=COMPONENTS, min_events=args.min_events)
    _print_lifts(lifts)

    if not lifts:
        print("기록할 lift가 없다 — 현재 활성 버전을 그대로 둔다(내리려면 --deactivate-all).")
        return
    if args.dry_run:
        print("dry-run — 기록하지 않는다.")
        return

    source = f"offline_batch_real_{date.today().isoformat()}"
    version = write_cluster_lifts(lifts, source=source)
    print(f"cluster_weight_config 버전 {version} 기록·전환 완료 (source={source})")
    print("롤백하려면 이전 버전 번호로 --activate-version을 실행한다.")


if __name__ == "__main__":
    main()
