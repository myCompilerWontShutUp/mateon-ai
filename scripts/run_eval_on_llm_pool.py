"""`scripts/run_eval.py`와 같은 Hit@10/NDCG 4종 비교(①임베딩만/②프로덕션/③보정모델/④단순추론)를
`scripts/generate_eval_definitions_llm.py`가 만든 gpt-5.6-terra 생성 풀(결정론적 조합 대신 실제
LLM이 생성한 팀·유저 50개씩)에 대해 돌린다(2026-08-20, 사용자 요청 — "터미널에서 실행할 수 있게
설정").

**`run_eval.py`와 다른 점 하나: ③번 lift를 Supabase에 쓰지 않고 로컬에서만 계산한다.** 이미
Supabase에 기록된 BE:beginner 등의 lift 값은 `docs/monitoring/cluster-weight-audit-trail-
example.md`가 참조하는 값이라, 이번 실험 데이터로 덮어쓰면 그 문서의 재현성이 깨진다. 그래서
이 스크립트는 "실제 서비스 읽기 경로"까지 검증하진 않고, 순수 알고리즘 비교만 한다.

사전 준비(순서대로 실행 필요, 이미 한 번 돌려서 캐시가 있으면 건너뜀):
  1. scripts/generate_eval_definitions_llm.py  (gpt-5.6-terra로 팀·유저 50개씩 구조화 필드 생성)
  2. 이 스크립트 — 팀/유저 임베딩·정답 라벨은 캐시가 있으면 재사용, 없으면 API 호출 후 캐싱

data/eval_llm_pool_*.json 은 전부 비결정론적 LLM 산출물이 섞여 있어 .gitignore에 등록돼
있다(원본 생성 캐시와 같은 취급).
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import get_settings  # noqa: E402
from app.core.prompts import load_prompt  # noqa: E402
from app.evaluation.metrics import graded_ndcg_at_k, hit_at_k, ndcg_at_k  # noqa: E402
from app.evaluation.schemas import GroundTruthLabel, NaiveRankingResult  # noqa: E402
from app.evaluation.scoring_arms import corrected_ranking, embedding_only_ranking, production_ranking  # noqa: E402
from app.evaluation.simulation import true_preference_score  # noqa: E402
from app.features.team_embedding.template import render_team_embedding_text  # noqa: E402
from app.features.user_to_team.template import render_intent_embedding_text  # noqa: E402
from app.openai_client.client import get_openai_client  # noqa: E402
from app.openai_client.embedding import embed_text  # noqa: E402
from app.openai_client.extraction import extract_structured  # noqa: E402
from app.schemas.contest import ContestField  # noqa: E402
from app.schemas.role_codes import ExperienceLevel, RoleCode  # noqa: E402
from app.schemas.team_extraction import TeamEmbeddingRefreshRequest, TeamSoftFields  # noqa: E402
from app.schemas.user_intent import UserIntentFields  # noqa: E402
from app.scoring.cluster import user_cluster_key  # noqa: E402
from app.scoring.cluster_weights import compute_weight_lifts  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GENERATED_INPUT = DATA_DIR / "eval_llm_generated_definitions_cache.json"
TEAMS_CACHE = DATA_DIR / "eval_llm_pool_teams.json"
USERS_CACHE = DATA_DIR / "eval_llm_pool_users.json"
GROUND_TRUTH_CACHE = DATA_DIR / "eval_llm_pool_ground_truth.json"
EVENTS_OUTPUT = DATA_DIR / "eval_llm_pool_synthetic_selections.json"
REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "monitoring" / "hit-at-10-eval-report-llm-pool.md"

K = 10
_COMPONENTS = ["similarity", "role_match", "deficit_fit", "beginner_fit", "activity_style_match"]
_GT_PROMPT = load_prompt("eval_ground_truth_labeling")
_NAIVE_PROMPT = load_prompt("eval_naive_ranking")


def _team_summary_lines(teams: dict) -> str:
    lines = []
    for team_id, team in sorted(teams.items(), key=lambda kv: int(kv[0])):
        meta = team["metadata"]
        lines.append(
            f"- team_id={team_id}: 모집역할={meta['recruiting_roles']}, "
            f"요구스킬={meta['required_skills']}, 활동방식={meta['activity_style']}, "
            f"초보자가능={meta['beginner_friendly']}, 공모전분야={meta['contest_field']}"
        )
    return "\n".join(lines)


def _user_summary(user: dict) -> str:
    meta = user["metadata"]
    return (
        f"희망역할={meta['desired_roles']}, 스킬={meta['skills']}, "
        f"활동방식={meta['activity_style']}, 경험수준={meta['experience_level']}"
    )


async def _build_teams() -> dict:
    raw = json.loads(GENERATED_INPUT.read_text(encoding="utf-8"))["teams"]
    teams = {}
    for i, t in enumerate(raw, start=1):
        request = TeamEmbeddingRefreshRequest(
            intro_text=t["intro_text"],
            recruiting_roles=t["recruiting_roles"],
            required_skills=t["required_skills"],
            contest_field=t["contest_field"],
        )
        soft_fields = TeamSoftFields(
            activity_goal=t["activity_goal"],
            activity_style=t["activity_style"],
            activity_intensity=t["activity_intensity"],
            beginner_friendly=t["beginner_friendly"],
            team_atmosphere=t["team_atmosphere"],
            recruiting_roles=[RoleCode(r) for r in t["recruiting_roles"]],
            contest_field=ContestField(t["contest_field"]) if t["contest_field"] else None,
        )
        embedding_text = render_team_embedding_text(request, soft_fields)
        vector = await embed_text(embedding_text)
        teams[str(i)] = {
            "team_id": i,
            "embedding_text": embedding_text,
            "embedding_vector": vector,
            "metadata": {
                "recruiting_roles": [r.value for r in soft_fields.recruiting_roles],
                "required_skills": request.required_skills,
                "activity_style": soft_fields.activity_style,
                "beginner_friendly": soft_fields.beginner_friendly,
                "contest_field": soft_fields.contest_field.value if soft_fields.contest_field else None,
            },
        }
        print(f"[team {i}/50] embedded")
    return teams


async def _build_users() -> dict:
    raw = json.loads(GENERATED_INPUT.read_text(encoding="utf-8"))["users"]
    users = {}
    for i, u in enumerate(raw, start=1):
        fields = UserIntentFields(
            desired_roles=[RoleCode(r) for r in u["desired_roles"]],
            skills=u["skills"],
            interests=u["interests"],
            activity_goal=u["activity_goal"],
            activity_style=u["activity_style"],
            experience_level=ExperienceLevel(u["experience_level"]),
        )
        embedding_text = render_intent_embedding_text(u["conversation_text"], fields)
        vector = await embed_text(embedding_text)
        users[str(i)] = {
            "user_id": i,
            "embedding_text": embedding_text,
            "embedding_vector": vector,
            "metadata": {
                "desired_roles": [r.value for r in fields.desired_roles],
                "skills": fields.skills,
                "activity_style": fields.activity_style,
                "experience_level": fields.experience_level.value if fields.experience_level else None,
            },
        }
        print(f"[user {i}/50] embedded")
    return users


async def _build_ground_truth(teams: dict, users: dict) -> dict:
    settings = get_settings()
    team_summary = _team_summary_lines(teams)
    results = {}
    for user_id, user in sorted(users.items(), key=lambda kv: int(kv[0])):
        prompt = f"[사용자 프로필]\n{_user_summary(user)}\n\n[팀 목록]\n{team_summary}"
        label = await extract_structured(
            messages=[
                {"role": "system", "content": _GT_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_model=GroundTruthLabel,
            model=settings.openai_judge_model,
        )
        results[user_id] = label.model_dump()
        print(f"[gt user {user_id}] relevant={label.relevant_team_ids}")
    return results


def _build_synthetic_selections(teams: dict, users: dict, ground_truth: dict) -> list[dict]:
    events = []
    for user_id, user in users.items():
        relevant_ids = set(ground_truth.get(user_id, {}).get("relevant_team_ids", []))
        if not relevant_ids:
            continue
        ranked = production_ranking(user["embedding_vector"], user["metadata"], teams)
        shown_candidates = [
            {
                "candidate_id": c.candidate_id,
                "total_score": c.total_score,
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
                "chooser_cluster_key": cluster_key,
                "selected_candidate_id": selected.candidate_id,
                "shown_candidates": shown_candidates,
            }
        )
    return events


async def _naive_ranking(user_summary: str, team_summary: str) -> tuple[list[int], int, int]:
    settings = get_settings()
    client = get_openai_client()
    prompt = f"[사용자 프로필]\n{user_summary}\n\n[팀 목록]\n{team_summary}"
    completion = await client.chat.completions.parse(
        model=settings.openai_llm_model,
        messages=[{"role": "system", "content": _NAIVE_PROMPT}, {"role": "user", "content": prompt}],
        response_format=NaiveRankingResult,
    )
    parsed = completion.choices[0].message.parsed
    usage = completion.usage
    return parsed.ranked_team_ids, usage.prompt_tokens, usage.completion_tokens


async def main() -> None:
    if not GENERATED_INPUT.exists():
        raise SystemExit(
            f"{GENERATED_INPUT} 없음 — 먼저 `uv run python scripts/generate_eval_definitions_llm.py`를 실행하세요."
        )

    if TEAMS_CACHE.exists() and USERS_CACHE.exists():
        print("팀/유저 임베딩 캐시 재사용 (API 재호출 없음)")
        teams = json.loads(TEAMS_CACHE.read_text(encoding="utf-8"))
        users = json.loads(USERS_CACHE.read_text(encoding="utf-8"))
    else:
        teams = await _build_teams()
        TEAMS_CACHE.write_text(json.dumps(teams, ensure_ascii=False), encoding="utf-8")
        users = await _build_users()
        USERS_CACHE.write_text(json.dumps(users, ensure_ascii=False), encoding="utf-8")

    if GROUND_TRUTH_CACHE.exists():
        print("정답 라벨 캐시 재사용 (API 재호출 없음)")
        ground_truth = json.loads(GROUND_TRUTH_CACHE.read_text(encoding="utf-8"))
    else:
        ground_truth = await _build_ground_truth(teams, users)
        GROUND_TRUTH_CACHE.write_text(json.dumps(ground_truth, ensure_ascii=False), encoding="utf-8")

    events = _build_synthetic_selections(teams, users, ground_truth)
    EVENTS_OUTPUT.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    lifts = compute_weight_lifts(events, components=_COMPONENTS)

    arm_keys = ("embedding_only", "production", "corrected", "naive_llm")
    records: list[dict] = []
    naive_prompt_tokens = naive_completion_tokens = naive_calls = 0
    naive_elapsed = 0.0
    skipped_users = 0
    team_summary = _team_summary_lines(teams)

    for user_id, user in sorted(users.items(), key=lambda kv: int(kv[0])):
        relevant_ids = set(ground_truth.get(user_id, {}).get("relevant_team_ids", []))
        if not relevant_ids:
            skipped_users += 1
            continue

        ranked_embed = embedding_only_ranking(user["embedding_vector"], teams)
        prod_scores = production_ranking(user["embedding_vector"], user["metadata"], teams)
        ranked_prod = [c.candidate_id for c in prod_scores]

        preference_relevance = {
            c.candidate_id: true_preference_score(c) for c in prod_scores if c.candidate_id in relevant_ids
        }
        true_pref_id = max(preference_relevance, key=preference_relevance.get)

        cluster_key = user_cluster_key(
            user["metadata"].get("desired_roles", []), user["metadata"].get("experience_level")
        )
        user_lifts = lifts.get(cluster_key, {})
        corrected_scores = corrected_ranking(user["embedding_vector"], user["metadata"], teams, user_lifts)
        ranked_corrected = [c.candidate_id for c in corrected_scores]

        start = time.monotonic()
        ranked_naive, ptok, ctok = await _naive_ranking(_user_summary(user), team_summary)
        naive_elapsed += time.monotonic() - start
        naive_prompt_tokens += ptok
        naive_completion_tokens += ctok
        naive_calls += 1

        ranked_by_arm = {
            "embedding_only": ranked_embed,
            "production": ranked_prod,
            "corrected": ranked_corrected,
            "naive_llm": ranked_naive,
        }
        record = {"user_id": user_id, "affected": bool(user_lifts)}
        for arm, ranked in ranked_by_arm.items():
            record[f"hit_{arm}"] = hit_at_k(ranked, relevant_ids, K)
            record[f"ndcg_{arm}"] = ndcg_at_k(ranked, relevant_ids, K)
            record[f"pref_ndcg_{arm}"] = graded_ndcg_at_k(ranked, preference_relevance, K)
            record[f"recovery_{arm}"] = 1.0 if ranked and ranked[0] == true_pref_id else 0.0
        records.append(record)
        print(f"user {user_id} scored (cluster={cluster_key}, affected={record['affected']})")

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
    overall = summarize(records)
    affected_summary = summarize(affected) if affected else None
    flipped = [r["user_id"] for r in records if r["recovery_production"] != r["recovery_corrected"]]

    arm_labels = {
        "embedding_only": "① 임베딩만",
        "production": "② 임베딩+메타데이터 (현재 프로덕션)",
        "corrected": "③ 임베딩+메타데이터+보정모델(로컬 lift)",
        "naive_llm": "④ 단순추론 (LLM 직접 순위)",
    }

    def render_table(summary: dict[str, dict[str, float]]) -> list[str]:
        lines = [
            "| 비교군 | Hit@10 | NDCG@10 (LLM 정답 기준) | NDCG@10 (선호 시나리오 기준) | 선호 회복률 |",
            "|---|---|---|---|---|",
        ]
        for key in arm_keys:
            s = summary[key]
            lines.append(
                f"| {arm_labels[key]} | {s['hit']:.3f} | {s['ndcg']:.3f} | {s['pref_ndcg']:.3f} | {s['recovery']:.3f} |"
            )
        return lines

    lines = ["# gpt-5.6-terra 생성 풀 기준 Hit@10/NDCG 평가 리포트", ""]
    lines.append(
        f"평가 대상: 유저 {len(users) - skipped_users}명(정답 없어 제외 {skipped_users}명), "
        f"팀 {len(teams)}개, K={K}"
    )
    lines.append(
        "③번 lift는 Supabase에 쓰지 않고 로컬 계산만 사용했다 — "
        "`docs/monitoring/cluster-weight-audit-trail-example.md`가 참조하는 라이브 값을 "
        "이번 실험 데이터로 덮어쓰지 않기 위함. 그래서 이 리포트는 실제 서비스 읽기 경로가 아니라 "
        "순수 알고리즘 비교만 검증한다."
    )
    lines.append(f"② → ③ 1위 추천이 실제로 바뀐 유저: {len(flipped)}/{len(records)}명 {flipped}")
    lines.append("")
    lines.append("## 전체 평균")
    lines.append("")
    lines += render_table(overall)
    if affected_summary:
        lines.append("")
        lines.append(f"## 보정이 실제로 적용된 유저만 ({len(affected)}/{len(records)}명)")
        lines.append("")
        lines += render_table(affected_summary)

    settings = get_settings()
    # 참고 단가(gpt-4.1-mini 기준) — run_eval.py와 동일한 참고치, 실제 모델 단가와 다를 수 있음.
    input_cost = naive_prompt_tokens / 1_000_000 * 0.40
    output_cost = naive_completion_tokens / 1_000_000 * 1.60
    lines += [
        "",
        "## ④ 단순추론 비용/지연",
        "",
        f"- 모델: `{settings.openai_llm_model}`, 호출 {naive_calls}회, "
        f"총 {naive_prompt_tokens + naive_completion_tokens} 토큰",
        f"- 평균 응답 시간: {naive_elapsed / naive_calls if naive_calls else 0:.2f}초, "
        f"추정 비용(gpt-4.1-mini 참고 단가 기준, 실제 단가와 다를 수 있음): "
        f"${input_cost + output_cost:.4f}",
        "",
        "## 방법론 노트",
        "",
        "- 팀·유저 구조화 필드는 `scripts/generate_eval_definitions_llm.py`가 `gpt-5.6-terra`로 "
        "생성한 것이다(결정론적 조합이 아님) — `data/eval_llm_generated_definitions_cache.json`, "
        "비결정론적 산출물이라 `.gitignore` 대상.",
        "- 임베딩/정답 라벨/이 리포트 자체를 포함해 `data/eval_llm_pool_*.json`도 같은 이유로 "
        "`.gitignore` 대상이다 — 재현하려면 `generate_eval_definitions_llm.py` → 이 스크립트 순으로 "
        "다시 실행한다.",
        "- 나머지 방법론(정답 라벨링·선호 시뮬레이션·선호 회복률 정의 등)은 "
        "`scripts/run_eval.py`(결정론적 데이터 버전)와 완전히 동일하다.",
    ]

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote report to {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
