"""`train_cluster_weight_ml_pretrain.py`와 동일한 작업(로지스틱 회귀 학습 + matplotlib 시각화)을
gpt-5.6-terra 데이터만 따로 떼어서 진행한다(2026-08-21, 사용자 요청 — "5.6 terra도 동일한 작업으로
진행"). Hit@10 평가를 "결정론적 데이터셋"과 "gpt-5.6-terra 데이터셋"으로 나눠 각각 따로 돌렸던
것과 같은 패턴이다.

**새 API 호출이 필요 없다** — `ml_pretrain_dummy_events` 테이블에 이미 저장해둔
`source='gpt-5.6-terra_pool'` 이벤트 50건을 Supabase에서 그대로 읽어와 재사용한다("두고두고
사용"하겠다던 원래 목적을 실제로 검증하는 실행이기도 하다).
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.evaluation.ml_pretrain import COMPONENTS, learn_ml_weights  # noqa: E402
from app.features.user_to_team.scoring import WEIGHTS  # noqa: E402
from app.scoring.cluster_weights import adjust_weights, compute_weight_lifts  # noqa: E402
from app.supabase_client.client import get_supabase_client  # noqa: E402

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

REPO_ROOT = Path(__file__).resolve().parent.parent
FIGURE_OUT = REPO_ROOT / "data" / "ml_pretrain_weight_comparison_gpt56terra.png"


def load_gpt56terra_events() -> list[dict]:
    client = get_supabase_client()
    res = client.table("ml_pretrain_dummy_events").select(
        "chooser_cluster_key,shown_candidates,selected_candidate_id"
    ).eq("source", "gpt-5.6-terra_pool").execute()
    return res.data


def main() -> None:
    print("Supabase(ml_pretrain_dummy_events, source=gpt-5.6-terra_pool)에서 이벤트 로드 중...")
    events = load_gpt56terra_events()
    print(f"gpt-5.6-terra 이벤트 {len(events)}건 로드 완료 (API 재호출 없음, 저장된 데이터 재사용)")

    result = learn_ml_weights(events)
    print(f"학습 데이터: {result['n_rows']}행, 양성(선택됨) 비율 {result['positive_rate']:.3f}, "
          f"GroupKFold {result['n_splits']}겹, 선택된 정규화 강도 C={result['best_C']:.4g}")
    print("학습된 원시 계수:", {k: round(v, 4) for k, v in result["raw_coef"].items()})
    ml_weights_dict = result["weights"]
    print("ML 학습 가중치(음수 클립 후 정규화):", {k: round(v, 4) for k, v in ml_weights_dict.items()})

    global_events = [{**e, "chooser_cluster_key": "GLOBAL"} for e in events]
    global_lift = compute_weight_lifts(global_events, components=COMPONENTS).get("GLOBAL", {})
    heuristic_weights = adjust_weights(WEIGHTS, global_lift)
    print("휴리스틱(현재 방식) 글로벌 lift:", {k: round(v, 4) for k, v in global_lift.items()})
    print("휴리스틱 조정 가중치:", {k: round(v, 4) for k, v in heuristic_weights.items()})

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(COMPONENTS))
    width = 0.25

    ax.bar(x - width, [WEIGHTS[c] for c in COMPONENTS], width, label="① 기본 WEIGHTS(고정)")
    ax.bar(x, [heuristic_weights[c] for c in COMPONENTS], width, label="② 휴리스틱 보정(현재 방식, lift=평균차)")
    ax.bar(x + width, [ml_weights_dict[c] for c in COMPONENTS], width, label="③ 로지스틱 회귀 학습(정식 ML)")

    ax.set_xticks(x)
    ax.set_xticklabels(COMPONENTS, rotation=15)
    ax.set_ylabel("가중치")
    ax.set_title("gpt-5.6-terra 데이터 전용 — 컴포넌트별 가중치 비교 (Supabase 저장분 재사용, 이벤트 50건)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURE_OUT, dpi=150)
    print(f"\n그래프 저장: {FIGURE_OUT} (로컬 전용, 커밋/업로드 안 함)")


if __name__ == "__main__":
    main()
