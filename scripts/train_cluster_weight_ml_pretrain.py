"""정식 ML(로지스틱 회귀) 사전 구축 실험 — 사용자 요청: "ML을 미리 만들어둘 수 있나" +
"더미데이터 양산해서 테스트" + "결과를 로컬 matplotlib으로 시각화"(2026-08-21).

**핵심 전제**: 이 모델은 실 선택 데이터가 아니라 더미 데이터로 학습하므로, 예측값 자체는
의미가 없다 — 학습·서빙 파이프라인이 기계적으로 작동하는지만 검증한다. 실 데이터가 쌓이면
이 스크립트를 실 `cluster_selection_events`로 다시 돌려야 한다.

더미 선택 이벤트는 결정론적 eval_definitions 풀(50)과 gpt-5.6-terra 풀(50)을 합쳐 100개
"선택 세션"으로 만든다(기존 생성 캐시 재사용, API 재호출 없음).

방식: 각 후보를 "선택됨(1)/안됨(0)" 이진 라벨로 펼쳐서, 컴포넌트 점수(similarity/role_match/
deficit_fit/beginner_fit/activity_style_match)를 피처로 로지스틱 회귀를 학습한다. 학습된
계수(coefficient)가 정식 ML 버전의 "가중치"에 해당한다 — 지금 쓰는 휴리스틱(lift = 평균 차이)과
같은 역할을 하는 값을 실제로 최적화(경사하강)로 얻는다는 점이 다르다.

더미 이벤트를 Supabase `cluster_selection_events`에는 절대 쓰지 않는다 — 그 테이블은
`run_cluster_weight_batch.py`가 source 구분 없이 전부 "실 데이터"로 취급하므로, 더미를 넣으면
나중에 실 데이터가 들어와도 걸러낼 방법이 없다(2026-08-21 확인). 대신 결과는 로컬 파일로만
저장한다(`data/ml_pretrain_dummy_events.json`, `.gitignore` 대상). Supabase에 durable하게
남기고 싶으면 `supabase/migrations/20260821000000_create_ml_pretrain_dummy_events.sql`을
SQL Editor에서 먼저 적용해야 한다(이 스크립트가 DDL을 실행할 방법이 없음).

**2026-08-21 학습 방식 개선**: 처음엔 클래스 불균형(양성 비율 ~2%)을 무시하고 정규화 강도
튜닝도 없이 전체 데이터로 한 번만 fit했다 — 사용자 지적으로 `class_weight='balanced'` +
`LogisticRegressionCV`(GroupKFold로 같은 선택 세션 내 후보가 train/validation에 걸쳐 섞이는
정보 누수 방지) 조합으로 고쳤다. 실제 학습 로직은 `app/evaluation/ml_pretrain.py`에 모아서
`_gpt56terra.py`/`eval_ml_pretrain_weights.py`와 공유한다.
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.evaluation.ml_pretrain import COMPONENTS, learn_ml_weights  # noqa: E402
from app.evaluation.scoring_arms import production_ranking  # noqa: E402
from app.evaluation.simulation import true_preference_score  # noqa: E402
from app.features.user_to_team.scoring import WEIGHTS  # noqa: E402
from app.scoring.cluster import user_cluster_key  # noqa: E402
from app.scoring.cluster_weights import adjust_weights, compute_weight_lifts  # noqa: E402

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False  # Malgun Gothic엔 유니코드 마이너스 글리프가 없음

REPO_ROOT = Path(__file__).resolve().parent.parent

DUMMY_EVENTS_OUT = REPO_ROOT / "data" / "ml_pretrain_dummy_events.json"
FIGURE_OUT = REPO_ROOT / "data" / "ml_pretrain_weight_comparison.png"


def _build_events(teams_path: Path, users_path: Path, ground_truth_path: Path, source_tag: str) -> list[dict]:
    teams = json.loads(teams_path.read_text(encoding="utf-8"))
    users = json.loads(users_path.read_text(encoding="utf-8"))
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))

    events = []
    for user_id, user in users.items():
        relevant_ids = set(ground_truth.get(user_id, {}).get("relevant_team_ids", []))
        if not relevant_ids:
            continue
        ranked = production_ranking(user["embedding_vector"], user["metadata"], teams)
        shown_candidates = [
            {
                "candidate_id": c.candidate_id,
                "component_scores": {"similarity": c.similarity, **c.metadata_scores},
            }
            for c in ranked
        ]
        selected = max((c for c in ranked if c.candidate_id in relevant_ids), key=true_preference_score)
        cluster_key = user_cluster_key(
            user["metadata"].get("desired_roles", []), user["metadata"].get("experience_level")
        )
        events.append(
            {
                "source": source_tag,
                "chooser_cluster_key": cluster_key,
                "shown_candidates": shown_candidates,
                "selected_candidate_id": selected.candidate_id,
            }
        )
    return events


def build_dummy_dataset() -> list[dict]:
    events = []
    events += _build_events(
        REPO_ROOT / "tests" / "fixtures" / "eval_teams.json",
        REPO_ROOT / "tests" / "fixtures" / "eval_users.json",
        REPO_ROOT / "tests" / "fixtures" / "eval_ground_truth.json",
        "eval_definitions_deterministic",
    )
    events += _build_events(
        REPO_ROOT / "data" / "eval_llm_pool_teams.json",
        REPO_ROOT / "data" / "eval_llm_pool_users.json",
        REPO_ROOT / "data" / "eval_llm_pool_ground_truth.json",
        "gpt-5.6-terra_pool",
    )
    return events


def main() -> None:
    print("더미 선택 이벤트 생성 중 (기존 캐시 재사용, API 호출 없음)...")
    events = build_dummy_dataset()
    n_det = sum(1 for e in events if e["source"] == "eval_definitions_deterministic")
    n_llm = sum(1 for e in events if e["source"] == "gpt-5.6-terra_pool")
    print(f"총 {len(events)}건의 더미 선택 세션 (source별: {n_det}건 결정론적, {n_llm}건 gpt-5.6-terra)")

    DUMMY_EVENTS_OUT.parent.mkdir(exist_ok=True)
    DUMMY_EVENTS_OUT.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"로컬 저장: {DUMMY_EVENTS_OUT}")

    # ── 정식 ML: class_weight=balanced + GroupKFold 교차검증으로 C 튜닝한 로지스틱 회귀 ──
    result = learn_ml_weights(events)
    print(f"학습 데이터: {result['n_rows']}행, 양성(선택됨) 비율 {result['positive_rate']:.3f}, "
          f"GroupKFold {result['n_splits']}겹, 선택된 정규화 강도 C={result['best_C']:.4g}")
    print("학습된 원시 계수:", {k: round(v, 4) for k, v in result["raw_coef"].items()})
    ml_weights_dict = result["weights"]
    print("ML 학습 가중치(음수 클립 후 정규화):", {k: round(v, 4) for k, v in ml_weights_dict.items()})

    # ── 비교 대상: 현재 방식(휴리스틱 lift)이 같은 더미 데이터로 계산하면 어떤 값이 나오는가 ──
    global_events = [{**e, "chooser_cluster_key": "GLOBAL"} for e in events]
    global_lift = compute_weight_lifts(global_events, components=COMPONENTS).get("GLOBAL", {})
    heuristic_weights = adjust_weights(WEIGHTS, global_lift)
    print("휴리스틱(현재 방식) 글로벌 lift:", {k: round(v, 4) for k, v in global_lift.items()})
    print("휴리스틱 조정 가중치:", {k: round(v, 4) for k, v in heuristic_weights.items()})

    # ── matplotlib 시각화 (로컬 전용) ──
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(COMPONENTS))
    width = 0.25

    ax.bar(x - width, [WEIGHTS[c] for c in COMPONENTS], width, label="① 기본 WEIGHTS(고정)")
    ax.bar(x, [heuristic_weights[c] for c in COMPONENTS], width, label="② 휴리스틱 보정(현재 방식, lift=평균차)")
    ax.bar(x + width, [ml_weights_dict[c] for c in COMPONENTS], width, label="③ 로지스틱 회귀 학습(정식 ML, 더미 데이터)")

    ax.set_xticks(x)
    ax.set_xticklabels(COMPONENTS, rotation=15)
    ax.set_ylabel("가중치")
    ax.set_title("컴포넌트별 가중치 비교 — 고정 vs 휴리스틱 보정 vs 정식 ML(더미 데이터 학습)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURE_OUT, dpi=150)
    print(f"\n그래프 저장: {FIGURE_OUT} (로컬 전용, 커밋/업로드 안 함)")


if __name__ == "__main__":
    main()
