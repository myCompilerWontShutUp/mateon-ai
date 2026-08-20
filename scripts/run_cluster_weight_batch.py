"""1번 항목(오프라인 클러스터 가중치 재계산 배치) — CLAUDE.md "## 모니터링·데이터 기반 가중치
보정" 참고. AI 서버 프로세스 안에서 돌지 않고, 사람이 앱 업데이트 주기(1주~6개월)에 맞춰
로컬에서 수동 실행한다.

**실 `cluster_selection_events`가 아직 0건이면(BE 미연동)** `tests/fixtures/
eval_synthetic_selections.json`(2번 항목에서 만든 시뮬레이션 데이터)으로 자동 대체한다 — 실
데이터가 쌓이기 시작하면 이 스크립트를 다시 실행할 때 자동으로 실 데이터를 쓰게 된다(코드
변경 불필요, 아래 SYNTHETIC_MIN_EVENTS 임계값 참고).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 기본 cp949가 em dash(—) 등을 못 찍음

from app.scoring.cluster_weight_store import write_cluster_lifts  # noqa: E402
from app.scoring.cluster_weights import compute_weight_lifts  # noqa: E402
from app.supabase_client.client import get_supabase_client  # noqa: E402

SYNTHETIC_EVENTS_PATH = (
    Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_synthetic_selections.json"
)
COMPONENTS = ["similarity", "role_match", "deficit_fit", "beginner_fit", "activity_style_match"]

# 실 이벤트가 이보다 적으면 아직 배치를 돌릴 만큼 데이터가 안 쌓였다고 보고 합성 데이터로
# 대체한다 — compute_weight_lifts 자체의 min_events(클러스터당 최소 2건)와는 다른 상위 게이트.
REAL_DATA_MIN_TOTAL_EVENTS = 1


def _load_real_events() -> list[dict]:
    client = get_supabase_client()
    res = client.table("cluster_selection_events").select(
        "chooser_cluster_key,selected_candidate_id,shown_candidates"
    ).execute()
    return [
        {
            "chooser_cluster_key": row["chooser_cluster_key"],
            "selected_candidate_id": row["selected_candidate_id"],
            "shown_candidates": row["shown_candidates"],
        }
        for row in res.data
    ]


def _load_synthetic_events() -> list[dict]:
    return json.loads(SYNTHETIC_EVENTS_PATH.read_text(encoding="utf-8"))


def main() -> None:
    real_events = _load_real_events()
    if len(real_events) >= REAL_DATA_MIN_TOTAL_EVENTS:
        events = real_events
        source = "offline_batch_real_2026-08-20"
        print(f"실 cluster_selection_events {len(events)}건으로 배치 실행")
    else:
        events = _load_synthetic_events()
        source = "offline_batch_synthetic_demo_2026-08-20"
        print(
            f"실 cluster_selection_events가 {len(real_events)}건뿐이라(BE 미연동), "
            f"합성 데이터 {len(events)}건으로 대체 — 실 데이터가 아니다."
        )

    lifts = compute_weight_lifts(events, components=COMPONENTS)
    print(f"{len(lifts)}개 클러스터에서 유의미한 lift 발견")
    for cluster_key, cluster_lifts in lifts.items():
        print(f"  {cluster_key}: {cluster_lifts}")

    if not lifts:
        print("기록할 lift가 없어 종료합니다.")
        return

    write_cluster_lifts(lifts, source=source)
    print(f"cluster_weight_config에 기록 완료 (source={source})")


if __name__ == "__main__":
    main()
