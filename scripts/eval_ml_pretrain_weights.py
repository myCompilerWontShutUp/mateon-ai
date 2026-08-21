"""ML 사전 구축 실험(로지스틱 회귀)에서 학습한 가중치를 실제로 추천 스코어링에 꽂아서
Hit@10/NDCG/선호 회복률을 측정한다(2026-08-21, 사용자 요청: "두 모델 다 조정된 가중치로 실
점수 측정도 같이 해주세요"). `scripts/run_eval.py`/`run_eval_on_llm_pool.py`와 동일한 측정
방식이다 — ML 학습 가중치를 새 비교군으로 추가해서 같은 두 평가 데이터셋(결정론적/gpt-5.6-terra)
에 각각 돌린다.

**전제**: ML 가중치는 실 선택 데이터가 아니라 더미 데이터로 학습됐다 — 이 점수 측정도 "예측이
실제로 더 정확하다"를 증명하는 게 아니라 "학습된 가중치를 실제 스코어링에 꽂았을 때 파이프라인이
정상 작동하는가·순위가 어떻게 달라지는가"를 보는 것이다.

새 API 호출이 필요 없다 — 두 평가 데이터셋의 임베딩·정답 라벨 모두 기존 캐시를 재사용한다.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.evaluation.metrics import graded_ndcg_at_k, hit_at_k, ndcg_at_k  # noqa: E402
from app.evaluation.ml_pretrain import learn_ml_weights  # noqa: E402
from app.evaluation.scoring_arms import _build_candidates  # noqa: E402
from app.evaluation.simulation import true_preference_score  # noqa: E402
from app.features.user_to_team.scoring import PENALTY_RULES, WEIGHTS  # noqa: E402
from app.scoring.engine import rank  # noqa: E402
from app.supabase_client.client import get_supabase_client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
K = 10


def custom_weights_ranking(user_vector, user_metadata, teams, weights):
    candidates = _build_candidates(user_vector, user_metadata, teams)
    return rank(candidates, weights, PENALTY_RULES)


def evaluate_arm(ranking_fn, teams, users, ground_truth) -> dict:
    records = []
    for user_id, user in sorted(users.items(), key=lambda kv: int(kv[0])):
        relevant_ids = set(ground_truth.get(user_id, {}).get("relevant_team_ids", []))
        if not relevant_ids:
            continue
        scores = ranking_fn(user["embedding_vector"], user["metadata"], teams)
        ranked = [c.candidate_id for c in scores]
        preference_relevance = {
            c.candidate_id: true_preference_score(c) for c in scores if c.candidate_id in relevant_ids
        }
        true_pref_id = max(preference_relevance, key=preference_relevance.get)
        records.append(
            {
                "hit": hit_at_k(ranked, relevant_ids, K),
                "ndcg": ndcg_at_k(ranked, relevant_ids, K),
                "pref_ndcg": graded_ndcg_at_k(ranked, preference_relevance, K),
                "recovery": 1.0 if ranked and ranked[0] == true_pref_id else 0.0,
            }
        )
    n = len(records)
    return {
        "n": n,
        "hit": sum(r["hit"] for r in records) / n,
        "ndcg": sum(r["ndcg"] for r in records) / n,
        "pref_ndcg": sum(r["pref_ndcg"] for r in records) / n,
        "recovery": sum(r["recovery"] for r in records) / n,
    }


def load_dataset(teams_path, users_path, ground_truth_path):
    return (
        json.loads(teams_path.read_text(encoding="utf-8")),
        json.loads(users_path.read_text(encoding="utf-8")),
        json.loads(ground_truth_path.read_text(encoding="utf-8")),
    )


def main() -> None:
    # ── ML 가중치 두 개 재현(로컬 계산, API 호출 없음) ──
    combined_events = json.loads((REPO_ROOT / "data" / "ml_pretrain_dummy_events.json").read_text(encoding="utf-8"))
    combined_result = learn_ml_weights(combined_events)
    combined_ml_weights = combined_result["weights"]

    client = get_supabase_client()
    gpt56terra_events = client.table("ml_pretrain_dummy_events").select(
        "chooser_cluster_key,shown_candidates,selected_candidate_id"
    ).eq("source", "gpt-5.6-terra_pool").execute().data
    gpt56terra_result = learn_ml_weights(gpt56terra_events)
    gpt56terra_ml_weights = gpt56terra_result["weights"]

    print(f"모델 1(결정론적+gpt-5.6-terra 혼합) — C={combined_result['best_C']:.4g}, "
          f"양성비율={combined_result['positive_rate']:.3f}, 가중치:",
          {k: round(v, 4) for k, v in combined_ml_weights.items()})
    print(f"모델 2(gpt-5.6-terra 전용) — C={gpt56terra_result['best_C']:.4g}, "
          f"양성비율={gpt56terra_result['positive_rate']:.3f}, 가중치:",
          {k: round(v, 4) for k, v in gpt56terra_ml_weights.items()})

    datasets = {
        "결정론적 평가셋": load_dataset(
            REPO_ROOT / "tests" / "fixtures" / "eval_teams.json",
            REPO_ROOT / "tests" / "fixtures" / "eval_users.json",
            REPO_ROOT / "tests" / "fixtures" / "eval_ground_truth.json",
        ),
        "gpt-5.6-terra 평가셋": load_dataset(
            REPO_ROOT / "data" / "eval_llm_pool_teams.json",
            REPO_ROOT / "data" / "eval_llm_pool_users.json",
            REPO_ROOT / "data" / "eval_llm_pool_ground_truth.json",
        ),
    }

    arms = {
        "② 프로덕션 WEIGHTS(고정)": WEIGHTS,
        "모델 1: ML(혼합 데이터 학습)": combined_ml_weights,
        "모델 2: ML(gpt-5.6-terra 전용 학습)": gpt56terra_ml_weights,
    }

    lines = ["# ML 사전 구축 가중치 — 실제 추천 점수 측정 결과", ""]
    for dataset_name, (teams, users, ground_truth) in datasets.items():
        lines.append(f"## {dataset_name}")
        lines.append("")
        lines.append("| 비교군 | Hit@10 | NDCG@10 (LLM 정답 기준) | NDCG@10 (선호 시나리오 기준) | 선호 회복률 |")
        lines.append("|---|---|---|---|---|")
        for arm_name, weights in arms.items():
            result = evaluate_arm(
                lambda uv, um, t, w=weights: custom_weights_ranking(uv, um, t, w), teams, users, ground_truth
            )
            line = (
                f"| {arm_name} | {result['hit']:.3f} | {result['ndcg']:.3f} | "
                f"{result['pref_ndcg']:.3f} | {result['recovery']:.3f} |"
            )
            lines.append(line)
            print(f"[{dataset_name}] {arm_name}: {result}")
        lines.append("")

    out_path = REPO_ROOT / "data" / "ml_pretrain_weight_eval_report.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n리포트 저장: {out_path}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
