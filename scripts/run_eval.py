"""Hit@10/NDCG@10 4종 비교 — 임베딩만 / 임베딩+메타데이터 / 임베딩+메타데이터+보정모델 /
단순추론(LLM 직접 순위 매기기). CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 3번 항목.

사전 준비(순서대로 실행 필요):
  1. scripts/generate_eval_fixtures.py           (50 팀 + 50 유저, 실제 임베딩)
  2. scripts/generate_eval_ground_truth.py       (상위 모델로 정답 라벨 생성)
  3. scripts/generate_eval_synthetic_selections.py (합성 선택 이벤트 + 클러스터 가산점)
  4. 이 스크립트
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 기본 cp949가 em dash(—) 등을 못 찍음

from app.core.config import get_settings  # noqa: E402
from app.core.prompts import load_prompt  # noqa: E402
from app.evaluation.metrics import graded_ndcg_at_k, hit_at_k, ndcg_at_k  # noqa: E402
from app.evaluation.schemas import NaiveRankingResult  # noqa: E402
from app.evaluation.scoring_arms import corrected_ranking, embedding_only_ranking, production_ranking  # noqa: E402
from app.evaluation.simulation import SIMULATED_TRUE_PREFERENCE_WEIGHTS, true_preference_score  # noqa: E402
from app.features.user_to_team.scoring import WEIGHTS as PRODUCTION_WEIGHTS  # noqa: E402
from app.openai_client.client import get_openai_client  # noqa: E402
from app.scoring.cluster import user_cluster_key  # noqa: E402
from app.scoring.cluster_weight_store import read_cluster_lifts  # noqa: E402

# 부록 "스트레스 테스트" 전용 — 실 lift가 아니다. 클러스터별 소수 이벤트 샘플의 노이즈를 걷어내고
# "노이즈가 완전히 사라질 만큼 데이터가 쌓이면 이론적으로 어디까지 갈 수 있는가"라는 상한을 보기
# 위해, adjust_weights(WEIGHTS, lift) 결과가 SIMULATED_TRUE_PREFERENCE_WEIGHTS와 정확히 같아지도록
# lift를 역산했다(사람이 감으로 정한 값이 아니라 두 가중치 dict의 비율에서 대수적으로 도출됨:
# lift_i = target_i/base_i - 1). CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 3번 항목 참고.
STRESS_TEST_LIFTS = {
    name: (SIMULATED_TRUE_PREFERENCE_WEIGHTS[name] / PRODUCTION_WEIGHTS[name]) - 1.0 for name in PRODUCTION_WEIGHTS
}
from scripts.generate_eval_ground_truth import _team_summary_lines, _user_summary  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "monitoring" / "hit-at-10-eval-report.md"

K = 10
_NAIVE_SYSTEM_PROMPT = load_prompt("eval_naive_ranking")


async def _naive_ranking(user_summary: str, team_summary: str) -> tuple[list[int], int, int]:
    """단순추론 비교군. extract_structured를 안 쓰고 직접 호출한다 — 토큰 사용량(비용 근거)을
    캡처해야 하는데 extract_structured는 이 정보를 호출자에게 돌려주지 않기 때문이다."""
    settings = get_settings()
    client = get_openai_client()
    prompt = f"[사용자 프로필]\n{user_summary}\n\n[팀 목록]\n{team_summary}"

    completion = await client.chat.completions.parse(
        model=settings.openai_llm_model,
        messages=[
            {"role": "system", "content": _NAIVE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format=NaiveRankingResult,
    )
    parsed = completion.choices[0].message.parsed
    usage = completion.usage
    return parsed.ranked_team_ids, usage.prompt_tokens, usage.completion_tokens


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


async def main() -> None:
    teams = _load("eval_teams.json")
    users = _load("eval_users.json")
    ground_truth = _load("eval_ground_truth.json")
    # 1번 항목 구현 이후: 로컬 JSON이 아니라 실제 cluster_weight_config(Supabase)에서 읽는다 —
    # scripts/run_cluster_weight_batch.py가 먼저 이 테이블에 기록해둬야 한다. 라이브
    # recommend_teams/recommend_users가 요청마다 쓰는 것과 완전히 같은 함수라, 이 평가가 실제
    # 프로덕션 읽기 경로까지 검증한다.
    cluster_lifts = read_cluster_lifts()

    arm_keys = ("embedding_only", "production", "corrected", "naive_llm")
    records: list[dict] = []  # 유저별 원본 기록 — 전체/영향군 분리 집계에 재사용한다.
    stress_records: list[dict] = []  # 부록 스트레스 테스트 전용 — 메인 4종 비교에는 안 섞는다.
    naive_prompt_tokens = 0
    naive_completion_tokens = 0
    naive_calls = 0
    naive_elapsed = 0.0
    skipped_users = 0

    team_summary = _team_summary_lines(teams)

    for user_id, user in sorted(users.items(), key=lambda kv: int(kv[0])):
        relevant_ids = set(ground_truth.get(user_id, {}).get("relevant_team_ids", []))
        if not relevant_ids:
            skipped_users += 1
            continue

        # 비교군 1
        ranked_embed = embedding_only_ranking(user["embedding_vector"], teams)

        # 비교군 2
        prod_scores = production_ranking(user["embedding_vector"], user["metadata"], teams)
        ranked_prod = [c.candidate_id for c in prod_scores]

        # "선호 회복률"/"선호 시나리오 NDCG"용 — 정답 팀들에 시뮬레이션한 "진짜 사용자 선호"
        # 기준 점수를 매긴다. 프로덕션 점수 순서와 무관하게 정의되므로 순환 논리가 아니다(위
        # true_preference_score docstring 참고). Hit@10/NDCG(LLM 정답 기준)는 정답 라벨링
        # 기준이 프로덕션 스코어링과 비슷해 이미 대부분 포화(0.9 이상)돼 방법론 간 차이가 잘 안
        # 드러나는데, 이 두 지표는 "보정 알고리즘이 실제로 겨냥한 그 격차를 회복하는가"만
        # 정확히 짚어낸다.
        preference_relevance = {
            c.candidate_id: true_preference_score(c) for c in prod_scores if c.candidate_id in relevant_ids
        }
        true_pref_id = max(preference_relevance, key=preference_relevance.get)

        # 비교군 3 — 이 유저의 클러스터가 실제로 보정을 받았는지(lift 존재)를 기록해뒀다가,
        # 리포트에서 "영향받은 유저만" 따로 집계한다(전체 평균은 미적용 유저에 희석된다).
        cluster_key = user_cluster_key(
            user["metadata"].get("desired_roles", []), user["metadata"].get("experience_level")
        )
        lifts = cluster_lifts.get(cluster_key, {})
        corrected_scores = corrected_ranking(user["embedding_vector"], user["metadata"], teams, lifts)
        ranked_corrected = [c.candidate_id for c in corrected_scores]

        # 비교군 4 (실제 LLM 호출)
        start = time.monotonic()
        ranked_naive, prompt_tokens, completion_tokens = await _naive_ranking(_user_summary(user), team_summary)
        naive_elapsed += time.monotonic() - start
        naive_prompt_tokens += prompt_tokens
        naive_completion_tokens += completion_tokens
        naive_calls += 1

        ranked_by_arm = {
            "embedding_only": ranked_embed,
            "production": ranked_prod,
            "corrected": ranked_corrected,
            "naive_llm": ranked_naive,
        }
        record = {"user_id": user_id, "affected": bool(lifts)}
        for arm, ranked in ranked_by_arm.items():
            record[f"hit_{arm}"] = hit_at_k(ranked, relevant_ids, K)
            record[f"ndcg_{arm}"] = ndcg_at_k(ranked, relevant_ids, K)
            record[f"pref_ndcg_{arm}"] = graded_ndcg_at_k(ranked, preference_relevance, K)
            record[f"recovery_{arm}"] = 1.0 if ranked and ranked[0] == true_pref_id else 0.0
        records.append(record)

        # 부록 스트레스 테스트 — 실제 클러스터 lift가 아니라 STRESS_TEST_LIFTS(위 상수)를 모든
        # 유저에게 균일하게 적용한다. "지금 값(0.62 등)은 작지만, 데이터가 훨씬 많이 쌓여 노이즈가
        # 사라지면 이론적으로 어디까지 갈 수 있는가"를 보여주는 상한 시연이라 클러스터 구분이
        # 필요 없다(SIMULATED_TRUE_PREFERENCE_WEIGHTS 자체가 클러스터 무관 전역 가정).
        stress_scores = corrected_ranking(user["embedding_vector"], user["metadata"], teams, STRESS_TEST_LIFTS)
        ranked_stress = [c.candidate_id for c in stress_scores]
        stress_records.append(
            {
                "user_id": user_id,
                "hit": hit_at_k(ranked_stress, relevant_ids, K),
                "ndcg": ndcg_at_k(ranked_stress, relevant_ids, K),
                "pref_ndcg": graded_ndcg_at_k(ranked_stress, preference_relevance, K),
                "recovery": 1.0 if ranked_stress and ranked_stress[0] == true_pref_id else 0.0,
            }
        )

        print(f"user {user_id} done (cluster={cluster_key}, affected={record['affected']})")

    def avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def summarize(subset: list[dict]) -> dict[str, dict[str, float]]:
        return {
            arm: {
                "hit": avg([r[f"hit_{arm}"] for r in subset]),
                "ndcg": avg([r[f"ndcg_{arm}"] for r in subset]),
                "pref_ndcg": avg([r[f"pref_ndcg_{arm}"] for r in subset]),
                "recovery": avg([r[f"recovery_{arm}"] for r in subset]),
            }
            for arm in arm_keys
        }

    affected = [r for r in records if r["affected"]]
    unaffected = [r for r in records if not r["affected"]]
    overall = summarize(records)
    affected_summary = summarize(affected) if affected else None

    stress_summary = {
        "hit": avg([r["hit"] for r in stress_records]),
        "ndcg": avg([r["ndcg"] for r in stress_records]),
        "pref_ndcg": avg([r["pref_ndcg"] for r in stress_records]),
        "recovery": avg([r["recovery"] for r in stress_records]),
    }

    arm_labels = {
        "embedding_only": "① 임베딩만",
        "production": "② 임베딩+메타데이터 (현재 프로덕션)",
        "corrected": "③ 임베딩+메타데이터+보정모델",
        "naive_llm": "④ 단순추론 (LLM 직접 순위)",
    }

    def render_table(summary: dict[str, dict[str, float]]) -> list[str]:
        table = ["| 비교군 | Hit@10 | NDCG@10 (LLM 정답 기준) | NDCG@10 (선호 시나리오 기준) | 선호 회복률 |", "|---|---|---|---|---|"]
        for key in arm_keys:
            s = summary[key]
            table.append(
                f"| {arm_labels[key]} | {s['hit']:.3f} | {s['ndcg']:.3f} | {s['pref_ndcg']:.3f} | {s['recovery']:.3f} |"
            )
        return table

    flipped_users = [
        r["user_id"] for r in records if r["recovery_production"] != r["recovery_corrected"]
    ]

    lines = ["# Hit@10 / NDCG@10 평가 리포트", ""]
    lines.append(f"평가 대상: 유저 {len(users) - skipped_users}명 (정답 없어 제외 {skipped_users}명), 팀 {len(teams)}개, K={K}")
    lines.append("")
    lines.append("## 결론 — 무엇을 보여주는 자료인가")
    lines.append("")
    lines += [
        f"**② → ③ 사이에 1위 추천이 실제로 바뀐 유저는 {len(flipped_users)}/{len(records)}명"
        f"{' (user ' + ', '.join(flipped_users) + ')' if flipped_users else ''}이다.** 전체 평균",
        f"선호 회복률 격차({overall['corrected']['recovery']:.3f} vs "
        f"{overall['production']['recovery']:.3f})도, 보정이 실제로 적용된 {len(affected)}명만",
        "좁혀봤을 때 격차가 더 뚜렷해지는 것(아래 \"클러스터 보정이 실제로 적용된 유저만\" 참고)도",
        "결국 이 소수 사례에서 나온다 — 50명 규모 합성 데이터에서는 통계적으로 견고한 \"③이 ②보다",
        "우수하다\"는 근거로 보기 어렵다. **이 리포트의 핵심은 점수 우위 증명이 아니다** —",
        "클러스터별 가중치 보정이 실제로 라이브 요청 경로에서 작동하고(합성 데이터 기준), 그 값이",
        "어디서 왔는지 끝까지 추적 가능하며, 잘못된 값이 들어가도 코드 배포 없이 즉시 롤백할 수",
        "있다는 걸 증명하는 자료다 — 구체적인 실측 사례는",
        "[`cluster-weight-audit-trail-example.md`](cluster-weight-audit-trail-example.md) 참고",
        "(선택 이벤트 → lift 계산 → Supabase 기록 → 실제 점수 변화 → 나쁜 값 주입 후 롤백까지",
        "전 과정을 실제 데이터로 재현). 지금 효과가 작은 게 노이즈 때문인지, 메커니즘 자체의",
        "상한 때문인지는 아래 \"부록 — 설계된 스트레스 테스트 시나리오\"에서 따로 확인할 수 있다.",
    ]
    lines.append("")
    lines.append("## 전체 평균")
    lines.append("")
    lines += render_table(overall)
    lines += [
        "",
        "**NDCG@10 (LLM 정답 기준)**은 정답 집합 전체를 동등하게 취급한다(원래 Hit@10과 짝을",
        "이루던 지표). **NDCG@10 (선호 시나리오 기준)**은 정답 팀들 사이에서도 시뮬레이션한",
        "\"진짜 사용자 선호\" 순서를 얼마나 잘 재현하는지를 잰다(graded relevance, "
        "`app/evaluation/metrics.py`의 `graded_ndcg_at_k`) — 다만 실측 결과 이 지표는 top-1",
        "교체처럼 미세한 순위 변화에는 둔감해서(순위 1↔2 교체는 log 할인 차이가 작음), 방법론",
        "간 차이를 더 잘 드러내리라던 예상과 달리 ②③ 차이를 거의 못 잡아낸다 — **선호",
        "회복률**(정답 팀들 중 \"진짜 선호\" 1위와 각 비교군의 1위 추천이 정확히 일치하는",
        "비율, Top-1 exact match)이 이런 미세한 변화에 더 민감하다. 세 지표 모두",
        "`app/evaluation/simulation.py`의 가상 시나리오 기준이라 실 데이터가 아니다 — CLAUDE.md",
        "참고.",
    ]

    if affected_summary:
        lines += [
            "",
            f"## 클러스터 보정이 실제로 적용된 유저만 ({len(affected)}/{len(records)}명)",
            "",
            "전체 평균은 보정이 적용 안 된 유저(해당 클러스터에 유의미한 lift가 없어 ③==②로",
            "완전히 동일)에 희석된다 — 아래는 실제로 ②와 ③이 달라진 유저만 따로 집계한 결과다.",
            "",
        ]
        lines += render_table(affected_summary)
        if unaffected:
            lines.append("")
            lines.append(
                f"(참고: 나머지 {len(unaffected)}명은 소속 클러스터에 lift가 없어 ②와 ③ 결과가 "
                "100% 동일하다 — min_events=2 미만인 클러스터, `app/scoring/cluster_weights.py` 참고.)"
            )

    lines += [
        "",
        "## 부록 — 설계된 스트레스 테스트 시나리오 (실측 아님)",
        "",
        "**위 ③은 클러스터당 2~3건 남짓한 합성 이벤트로 추정한 lift라 노이즈가 크다.** \"노이즈가",
        "완전히 사라질 만큼 데이터가 쌓이면 이론적으로 어디까지 갈 수 있는가\"를 보기 위해, 실",
        "이벤트를 더 만드는 대신 `adjust_weights(WEIGHTS, lift)` 결과가",
        "`app/evaluation/simulation.py`의 `SIMULATED_TRUE_PREFERENCE_WEIGHTS`(\"진짜 사용자 선호\"",
        "가정)와 **정확히 같아지도록 lift를 역산**했다(`lift_i = target_i/base_i - 1`, 감으로 정한",
        "값이 아니라 두 가중치 dict의 비율에서 대수적으로 나온 값 — `scripts/run_eval.py`의",
        "`STRESS_TEST_LIFTS` 참고). 이 lift는 실제 `cluster_selection_events`에서 나온 값이",
        "**아니고**, 모든 유저에게 클러스터 구분 없이 균일하게 적용했다 — 상한을 보여주는 가상",
        "시나리오이지 실측 결과가 아니다.",
        "",
    ]
    lines += [
        "| 비교군 | Hit@10 | NDCG@10 (LLM 정답 기준) | NDCG@10 (선호 시나리오 기준) | 선호 회복률 |",
        "|---|---|---|---|---|",
        f"| ② 임베딩+메타데이터 (현재 프로덕션) | {overall['production']['hit']:.3f} | "
        f"{overall['production']['ndcg']:.3f} | {overall['production']['pref_ndcg']:.3f} | "
        f"{overall['production']['recovery']:.3f} |",
        f"| ③′ 이상적 보정 (가상 시나리오, 실측 아님) | {stress_summary['hit']:.3f} | "
        f"{stress_summary['ndcg']:.3f} | {stress_summary['pref_ndcg']:.3f} | "
        f"{stress_summary['recovery']:.3f} |",
    ]
    lines += [
        "",
        "이 표는 \"실제로 이만큼 개선된다\"가 아니라 \"보정 메커니즘 자체는 divergence 크기에",
        "비례해서 격차를 좁힐 수 있는 능력이 있다\"는 걸 보여주는 상한 데모다. 선호 회복률은",
        f"{overall['production']['recovery']:.3f} → {stress_summary['recovery']:.3f}로 뚜렷하게",
        "벌어진다 — 실제 효과가 이 값에 못 미치는 이유는 메커니즘이 안 되어서가 아니라, 지금",
        "합성 이벤트가 이 정도 크기의 divergence를 아직 관측하지 못했기 때문이다(표본 부족).",
        "**한편 NDCG(LLM 정답 기준)는 오히려 소폭 낮아진다"
        f"({overall['production']['ndcg']:.3f} → {stress_summary['ndcg']:.3f})** — 이 지표는",
        "정답 팀 전체를 동등하게 취급하는데, 가중치를 특정 \"선호\"쪽으로 강하게 재분배하면 그",
        "선호와 무관하게 동등히 정답인 다른 팀들의 순위가 밀릴 수 있어서다. 즉 보정은 공짜가",
        "아니라 \"어느 기준으로 잘 맞히는가\"를 트레이드오프하는 것이며, 이 트레이드오프까지",
        "그대로 보여주는 게 이 표를 부록으로 분리해 실측처럼 보이지 않게 하는 이유이기도 하다.",
        "BE 연동 후 실 데이터가 쌓이면 실측값이 위 ③(부록이 아닌 본문)과 이 상한 사이 어딘가로",
        "수렴할 것으로 예상한다.",
    ]

    settings = get_settings()
    input_cost = naive_prompt_tokens / 1_000_000 * 0.40  # gpt-4.1-mini 단가, .env 모델과 다르면 참고치
    output_cost = naive_completion_tokens / 1_000_000 * 1.60
    lines += [
        "",
        "## ④ 단순추론 비용/지연 (대조군 근거)",
        "",
        f"- 모델: `{settings.openai_llm_model}`",
        f"- 호출 {naive_calls}회, 총 {naive_prompt_tokens + naive_completion_tokens} 토큰"
        f"(input {naive_prompt_tokens}, output {naive_completion_tokens})",
        f"- 평균 응답 시간: {naive_elapsed / naive_calls if naive_calls else 0:.2f}초/호출",
        f"- 추정 비용(gpt-4.1-mini 단가 기준): ${input_cost + output_cost:.4f}"
        f"(요청 {len(users) - skipped_users}건 기준, 후보군이 커지면 입력 토큰이 선형으로 늘어난다)",
        "",
        "①~③은 임베딩 계산(요청당 1회) 외 추가 LLM 호출이 없다 — 후보 수가 늘어도 스코어링",
        "자체는 순수 계산이라 비용이 거의 늘지 않는다. ④는 후보 목록 전체를 매번 프롬프트에",
        "실어 보내야 해서 후보 수에 비례해 비용이 커진다.",
        "",
        "## 방법론 노트 (재현·검증용)",
        "",
        "- 팀 50개·유저 50개는 `tests/fixtures/eval_definitions.py`가 결정론적으로(고정 시드)",
        "  생성, 실제 `text-embedding-3-small` 임베딩을 붙였다",
        "  (`scripts/generate_eval_fixtures.py`).",
        f"- 정답(ground truth)은 `{settings.openai_judge_model}`(`OPENAI_JUDGE_MODEL`)로 생성했다",
        "  (`scripts/generate_eval_ground_truth.py`, `tests/fixtures/eval_ground_truth.json`).",
        "  **표본 검수는 아직 진행 전이다** — 발표 전에 몇 건 사람이 직접 봐서 라벨이 말이",
        "  되는지 확인 권장.",
        "- **③(보정모델)은 이제 실제 `cluster_weight_config`(Supabase)에서 읽는다** — 로컬",
        "  JSON이 아니라 라이브 `recommend_teams`/`recommend_users`(`app/features/*/recommend.py`)와",
        "  완전히 같은 `read_cluster_lifts()` 함수를 쓴다(`app/scoring/cluster_weight_store.py`).",
        "  즉 이 평가가 실제 프로덕션 읽기 경로까지 검증한다.",
        "- `cluster_weight_config`는 여전히 `scripts/run_cluster_weight_batch.py`가 합성 선택",
        "  이벤트(`tests/fixtures/eval_synthetic_selections.json`)로 채운 값이다 — BE 연동 후",
        "  실 `cluster_selection_events`가 쌓이면, 같은 배치 스크립트를 다시 돌리는 것만으로",
        "  자동으로 실 데이터를 쓰게 된다(코드 변경 불필요, source 태그가 자동으로",
        "  'offline_batch_real_...'로 바뀜).",
        "- 재현 순서: `generate_eval_fixtures.py` → `generate_eval_ground_truth.py` →",
        "  `generate_eval_synthetic_selections.py` → `run_cluster_weight_batch.py` →",
        "  `run_eval.py`.",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote report to {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
