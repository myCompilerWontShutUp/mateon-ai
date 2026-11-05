"""실제 사용자 11명 + 그 형식을 따른 합성 89명(총 100명)으로 추천 방법을 다시 잰다.

이전 평가(`run_eval.py`, `run_eval_on_llm_pool.py`)의 약점을 고친 버전이다.

1. **입력이 프로필 화면 원문이다.** 이전엔 희망 역할·경험 수준이 이미 정리된 구조화 필드를 넣었다.
   이번엔 장점/기술분야/키워드 원문을 넣어, 파이프라인이 원문에서 역할과 경험을 뽑아내는 단계까지
   평가 대상에 포함한다.
2. **정답을 원문만 본 채점자가 만든다.** 이전 정답 프롬프트는 "실제 서비스 스코어링과 동일하게
   아래 4가지를 종합"하라고 서비스 채점 기준을 그대로 알려줘서, 정답이 우리 채점과 거의 같아졌다
   (NDCG 0.98 포화의 원인). 이번 채점자는 서비스 채점 기준도, 파이프라인 추출 결과도 모른다.
3. **기존 룰베이스를 비교군에 넣었다.** 백엔드 `EventMatchingService.matchInterestJob`을 그대로
   옮긴 `app/evaluation/legacy_rule_matching.py`.
4. **채점을 두 번 한다.** 팀 목록 순서를 다르게 섞어 두 번 채점해, 채점 자체가 얼마나 흔들리는지
   (그리고 목록 순서에 끌리는지) 같이 보고한다.
5. **지표를 적중률 중심으로 바꾸고 95% 신뢰구간을 붙였다.** NDCG는 뺐다.
6. **방법별 추천 속도와 LLM 호출 수를 같이 잰다.**

클러스터 보정(③)은 뺐다 — 보정의 입력인 선택 이벤트를 "가상의 진짜 선호"로 합성해야 해서 그
자체가 순환 논리이기 때문이다.

비교군:
    ① 의미만 보는 추천      임베딩 유사도만
    ② 에이전트 파이프라인    원문 → LLM 의도 추출 → 임베딩 + 조건 6개 축 (현재 서비스)
    ④ LLM에 직접 묻기       원문과 팀 목록을 LLM에 주고 순위를 바로 받음
    ⑤ 기존 룰베이스         희망직무 키워드 부분 문자열 매칭 (백엔드 원본)

사전 준비:
    uv run python scripts/generate_realistic_user_profiles.py   # 사용자 100명
    (팀 50개는 run_eval_on_llm_pool.py가 만든 캐시를 그대로 쓴다)

사용법:
    uv run python scripts/run_realistic_eval.py          # 단계별 캐시가 있으면 재사용
    uv run python scripts/run_realistic_eval.py --fresh  # 캐시 무시하고 전부 다시

API 호출이 드는 단계(파이프라인·채점·LLM 직접 순위)는 사용자 한 명 끝날 때마다 캐시에 저장한다
— 중간에 끊겨도 이미 돈 낸 결과는 남는다. 캐시(`data/eval_realistic_*.json`)는 실제 사용자 글이
섞여 있어 `.gitignore` 대상이고, 리포트에는 집계 수치만 쓴다.
"""

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
import zlib
from pathlib import Path

import openai

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import get_settings  # noqa: E402
from app.core.prompts import load_prompt  # noqa: E402
from app.evaluation.legacy_rule_matching import (  # noqa: E402
    interest_jobs_from_profile,
    legacy_rule_ranking,
    team_search_text,
)
from app.evaluation.metrics import precision_at_k, wilson_interval  # noqa: E402
from app.evaluation.schemas import BlindGroundTruthJudgment, NaiveRankingResult  # noqa: E402
from app.evaluation.scoring_arms import embedding_only_ranking, production_ranking  # noqa: E402
from app.features.user_to_team.chat_reply import OPENING_GREETING  # noqa: E402
from app.features.user_to_team.intent import compute_user_intent  # noqa: E402
from app.features.user_to_team.template import render_intent_embedding_text  # noqa: E402
from app.openai_client.client import get_openai_client  # noqa: E402
from app.openai_client.embedding import embed_text  # noqa: E402
from app.openai_client.extraction import extract_structured  # noqa: E402
from app.schemas.role_codes import ROLE_CODE_LABELS, RoleCode  # noqa: E402
from app.schemas.user_intent import ConversationMessage, UserIntentExtractionRequest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROFILES_PATH = DATA_DIR / "eval_realistic_profiles.json"
TEAMS_RAW_PATH = DATA_DIR / "eval_llm_generated_definitions_cache.json"
TEAMS_CACHE_PATH = DATA_DIR / "eval_llm_pool_teams.json"
PIPELINE_CACHE = DATA_DIR / "eval_realistic_pipeline.json"
JUDGE_CACHE = DATA_DIR / "eval_realistic_judgments.json"
NAIVE_CACHE = DATA_DIR / "eval_realistic_naive.json"
REPORT_PATH = ROOT / "docs" / "monitoring" / "realistic-eval-report.md"

JUDGE_PASSES = (("pass1", 1101), ("pass2", 2202))  # (이름, 팀 순서를 섞는 시드)
JUDGE_CONCURRENCY = 6
_JUDGE_PROMPT = load_prompt("eval_ground_truth_blind")
_NAIVE_PROMPT = load_prompt("eval_naive_ranking")

ARMS = ("embedding_only", "pipeline", "naive_llm", "legacy_rule")
ARM_LABELS = {
    "embedding_only": "① 의미만 보는 추천",
    "pipeline": "② 에이전트 파이프라인 (현재 서비스)",
    "naive_llm": "④ LLM에 직접 묻기",
    "legacy_rule": "⑤ 기존 룰베이스 (키워드 매칭)",
}


# ---------------------------------------------------------------- 공통


def _load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _save_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _role_label(code: str) -> str:
    try:
        return ROLE_CODE_LABELS[RoleCode(code)]
    except ValueError:
        return code


def _profile_text(profile: dict) -> str:
    keywords = " ".join(f"#{k}" for k in profile["keywords"]) if profile["keywords"] else "(없음)"
    return f"장점: {profile['strengths']}\n기술분야: {profile['tech_field']}\n키워드: {keywords}"


def _team_listing(teams_raw: dict[int, dict], order: list[int]) -> str:
    lines = []
    for team_id in order:
        team = teams_raw[team_id]
        roles = ", ".join(_role_label(r) for r in team["recruiting_roles"])
        lines.append(
            f"- team_id={team_id}: {team['intro_text']} / 모집 역할: {roles} / "
            f"필요 기술: {', '.join(team['required_skills'])} / 활동 목표: {team['activity_goal']} / "
            f"활동 방식: {team['activity_style']} / 초보자 환영: {'예' if team['beginner_friendly'] else '아니오'}"
        )
    return "\n".join(lines)


def _median_p90(values: list[float]) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    ordered = sorted(values)
    return statistics.median(ordered), ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))]


# ---------------------------------------------------------------- 1단계: 에이전트 파이프라인


async def _run_pipeline(profile: dict) -> dict:
    """실제 `/intents/extract` 서비스 함수를 그대로 부른다(구조화 추출 + 응답 문장 생성, LLM 2회).

    프로필 글은 인사말보다 앞에 `[자기소개서]` 라벨을 붙여 넣는다 — 서비스 계약 문서에 적힌
    "미리 등록된 자기소개서를 채팅 시작 전에 싣는" 방식 그대로다.
    """
    message = f"[자기소개서]\n{_profile_text(profile)}"
    request = UserIntentExtractionRequest(
        messages=[
            ConversationMessage(id=1, role="user", message=message),
            ConversationMessage(id=2, role="assistant", message=OPENING_GREETING),
        ]
    )

    started = time.perf_counter()
    result = await compute_user_intent(request)
    intent_seconds = time.perf_counter() - started

    vector = result.embedding_vector
    fallback_embed_seconds = 0.0
    if vector is None:
        # 필수 항목(희망 역할·경험 수준)이 비면 서비스는 임베딩을 주지 않고 추가 질문을 한다.
        # 평가에서는 추가 질문 답변을 지어내지 않고, 원문에서 뽑힌 만큼만으로 임베딩해 순위를 낸다
        # — 서비스보다 불리한 조건이며, 이런 사용자의 비율은 리포트에 따로 적는다.
        started = time.perf_counter()
        vector = await embed_text(render_intent_embedding_text(message, result.extracted))
        fallback_embed_seconds = time.perf_counter() - started

    fields = result.extracted
    return {
        "one_shot_complete": not result.missing_fields,
        "missing_fields": result.missing_fields,
        "intent_seconds": intent_seconds,
        "fallback_embed_seconds": fallback_embed_seconds,
        "embedding_vector": vector,
        "metadata": {
            "desired_roles": [r.value for r in fields.desired_roles],
            "skills": fields.skills,
            "activity_style": fields.activity_style,
            "experience_level": fields.experience_level.value if fields.experience_level else None,
            "activity_time": fields.optional.activity_time,
        },
    }


async def _stage_pipeline(profiles: list[dict], fresh: bool) -> dict:
    cache = {} if fresh else _load_json(PIPELINE_CACHE, {})
    todo = [p for p in profiles if p["id"] not in cache]
    print(f"\n[1/3] 에이전트 파이프라인 — {len(todo)}명 실행 (캐시 {len(cache)}명). 지연을 정확히 재려고 순차 실행")
    for index, profile in enumerate(todo, start=1):
        cache[profile["id"]] = await _run_pipeline(profile)
        _save_json(PIPELINE_CACHE, cache)
        entry = cache[profile["id"]]
        print(
            f"  {index}/{len(todo)} {profile['id']}: 역할={entry['metadata']['desired_roles']} "
            f"경험={entry['metadata']['experience_level']} 한번에완성={entry['one_shot_complete']} "
            f"{entry['intent_seconds']:.1f}s"
        )
    return cache


# ---------------------------------------------------------------- 2단계: 원문만 보는 채점(2회)


async def _judge_once(profile: dict, teams_raw: dict[int, dict], seed: int) -> dict:
    order = list(teams_raw)
    random.Random(seed + zlib.crc32(profile["id"].encode())).shuffle(order)
    prompt = f"[학생 프로필 원문]\n{_profile_text(profile)}\n\n[팀 모집글 목록]\n{_team_listing(teams_raw, order)}"
    valid_ids = set(teams_raw)

    for _attempt in range(3):
        judgment = await extract_structured(
            messages=[{"role": "system", "content": _JUDGE_PROMPT}, {"role": "user", "content": prompt}],
            response_model=BlindGroundTruthJudgment,
            model=get_settings().openai_judge_model,
        )
        if judgment.best_team_id in valid_ids:
            acceptable = sorted({t for t in judgment.acceptable_team_ids if t in valid_ids} | {judgment.best_team_id})
            return {
                "best_team_id": judgment.best_team_id,
                "acceptable_team_ids": acceptable,
                "rationale": judgment.rationale,
            }
    raise RuntimeError(f"{profile['id']}: 채점자가 목록에 없는 team_id를 반복해서 골랐다")


async def _stage_judge(profiles: list[dict], teams_raw: dict[int, dict], fresh: bool) -> dict:
    cache = {} if fresh else _load_json(JUDGE_CACHE, {})
    jobs = [(p, name, seed) for p in profiles for name, seed in JUDGE_PASSES if name not in cache.get(p["id"], {})]
    print(f"\n[2/3] 원문만 보는 채점 — {len(jobs)}건 실행 (사용자당 2회, 팀 순서를 매번 다르게 섞음)")
    semaphore = asyncio.Semaphore(JUDGE_CONCURRENCY)
    lock = asyncio.Lock()
    done = 0

    async def run(profile: dict, name: str, seed: int) -> None:
        nonlocal done
        async with semaphore:
            result = await _judge_once(profile, teams_raw, seed)
        async with lock:
            cache.setdefault(profile["id"], {})[name] = result
            _save_json(JUDGE_CACHE, cache)
            done += 1
            print(f"  {done}/{len(jobs)} {profile['id']} {name}: best={result['best_team_id']}")

    await asyncio.gather(*(run(*job) for job in jobs))
    return cache


# ---------------------------------------------------------------- 3단계: LLM에 직접 묻기


async def _naive_once(profile: dict, teams_raw: dict[int, dict]) -> dict:
    prompt = f"[사용자 프로필]\n{_profile_text(profile)}\n\n[팀 목록]\n{_team_listing(teams_raw, sorted(teams_raw))}"
    started = time.perf_counter()
    completion = await get_openai_client().chat.completions.parse(
        model=get_settings().openai_llm_model,
        messages=[{"role": "system", "content": _NAIVE_PROMPT}, {"role": "user", "content": prompt}],
        response_format=NaiveRankingResult,
    )
    seconds = time.perf_counter() - started

    ranked: list[int] = []
    for team_id in completion.choices[0].message.parsed.ranked_team_ids:
        if team_id in teams_raw and team_id not in ranked:
            ranked.append(team_id)
    return {
        "ranked": ranked,
        "seconds": seconds,
        "prompt_tokens": completion.usage.prompt_tokens,
        "completion_tokens": completion.usage.completion_tokens,
    }


async def _stage_naive(profiles: list[dict], teams_raw: dict[int, dict], fresh: bool) -> dict:
    cache = {} if fresh else _load_json(NAIVE_CACHE, {})
    todo = [p for p in profiles if p["id"] not in cache]
    print(f"\n[3/3] LLM에 직접 묻기 — {len(todo)}명 실행. 지연을 정확히 재려고 순차 실행")
    for index, profile in enumerate(todo, start=1):
        try:
            cache[profile["id"]] = await _naive_once(profile, teams_raw)
        except openai.RateLimitError as error:
            # 크레딧 소진·요청 한도 초과로 끊겨도 이미 측정한 사용자로 리포트는 만든다 — 다시 실행하면
            # 캐시에 없는 사용자부터 이어서 측정한다. ④ 표본이 줄어든 사실은 리포트에 명시된다.
            print(f"  ! LLM 직접 순위 중단 ({index - 1}/{len(todo)}명 추가 측정 후): {error}")
            break
        _save_json(NAIVE_CACHE, cache)
        print(f"  {index}/{len(todo)} {profile['id']}: {cache[profile['id']]['seconds']:.1f}s")
    return cache


# ---------------------------------------------------------------- 채점·집계


def _score_user(ranked: list[int], judgment: dict) -> dict:
    best = judgment["best_team_id"]
    acceptable = set(judgment["acceptable_team_ids"])
    return {
        "top1": 1.0 if ranked[:1] == [best] else 0.0,
        "top3": 1.0 if best in ranked[:3] else 0.0,
        "top10": 1.0 if best in ranked[:10] else 0.0,
        "useful3": precision_at_k(ranked, acceptable, 3),
    }


def _summarize(records: list[dict]) -> dict:
    """방법별로 측정된 사용자만 모아 집계한다 — 어떤 방법이 일부 사용자만 측정됐으면 그 인원이 n이다."""
    summary = {}
    for arm in ARMS:
        measured = [r for r in records if arm in r]
        n = len(measured)
        row = {"n": n}
        for metric in ("top1", "top3", "top10"):
            hits = int(sum(r[arm][metric] for r in measured))
            low, high = wilson_interval(hits, n)
            row[metric] = (hits / n if n else 0.0, low, high)
        row["useful3"] = sum(r[arm]["useful3"] for r in measured) / n if n else 0.0
        summary[arm] = row
    return summary


def _format_rate(value: tuple[float, float, float]) -> str:
    rate, low, high = value
    return f"{rate * 100:.0f}% ({low * 100:.0f}~{high * 100:.0f})"


def _render_summary_table(summary: dict, team_count: int) -> list[str]:
    lines = [
        "| 방법 | 1순위 적중 | 상위 3개 안 | 상위 10개 안 | 추천 3개 중 쓸 만한 팀 |",
        "|---|---|---|---|---|",
    ]
    full = max(row["n"] for row in summary.values())
    for arm in ARMS:
        row = summary[arm]
        if row["n"] == 0:
            lines.append(f"| {ARM_LABELS[arm]} | 측정 안 됨 | — | — | — |")
            continue
        label = ARM_LABELS[arm] + (f" *({row['n']}명만 측정)*" if row["n"] < full else "")
        lines.append(
            f"| {label} | {_format_rate(row['top1'])} | {_format_rate(row['top3'])} | "
            f"{_format_rate(row['top10'])} | {row['useful3'] * 100:.0f}% |"
        )
    lines.append(
        f"| *(참고) 무작위로 골랐을 때* | {100 / team_count:.0f}% | {300 / team_count:.0f}% | "
        f"{1000 / team_count:.0f}% | — |"
    )
    return lines


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true", help="모든 단계 캐시를 무시하고 다시 실행")
    args = parser.parse_args()

    if not PROFILES_PATH.exists():
        raise SystemExit("사용자 프로필이 없다 — 먼저 scripts/generate_realistic_user_profiles.py를 실행하세요.")
    if not TEAMS_CACHE_PATH.exists() or not TEAMS_RAW_PATH.exists():
        raise SystemExit("팀 캐시가 없다 — 먼저 scripts/run_eval_on_llm_pool.py를 한 번 실행하세요.")

    profiles = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))["profiles"]
    teams_raw = {i: t for i, t in enumerate(json.loads(TEAMS_RAW_PATH.read_text(encoding="utf-8"))["teams"], start=1)}
    teams = json.loads(TEAMS_CACHE_PATH.read_text(encoding="utf-8"))
    team_texts = {
        team_id: team_search_text(t["intro_text"], t["recruiting_roles"], t["required_skills"])
        for team_id, t in teams_raw.items()
    }

    pipeline = await _stage_pipeline(profiles, args.fresh)
    judgments = await _stage_judge(profiles, teams_raw, args.fresh)
    naive = await _stage_naive(profiles, teams_raw, args.fresh)

    records: list[dict] = []
    ranking_ms = {"embedding_only": [], "pipeline": [], "legacy_rule": []}
    legacy_zero_users = 0

    for profile in profiles:
        user_id = profile["id"]
        run = pipeline[user_id]

        started = time.perf_counter()
        ranked_embedding = [int(t) for t in embedding_only_ranking(run["embedding_vector"], teams)]
        ranking_ms["embedding_only"].append((time.perf_counter() - started) * 1000)

        started = time.perf_counter()
        ranked_pipeline = [int(c.candidate_id) for c in production_ranking(run["embedding_vector"], run["metadata"], teams)]
        ranking_ms["pipeline"].append((time.perf_counter() - started) * 1000)

        interest_jobs = interest_jobs_from_profile(profile["keywords"], profile["tech_field"])
        started = time.perf_counter()
        ranked_legacy, legacy_scores = legacy_rule_ranking(
            interest_jobs, team_texts, tie_break_seed=zlib.crc32(user_id.encode())
        )
        ranking_ms["legacy_rule"].append((time.perf_counter() - started) * 1000)
        if max(legacy_scores.values()) == 0:
            legacy_zero_users += 1

        ranked_by_arm = {
            "embedding_only": ranked_embedding,
            "pipeline": ranked_pipeline,
            "naive_llm": naive[user_id]["ranked"] if user_id in naive else None,
            "legacy_rule": ranked_legacy,
        }
        judgment = judgments[user_id]["pass1"]
        second = judgments[user_id]["pass2"]
        record = {
            "id": user_id,
            "origin": profile["origin"],
            "judges_agree": judgment["best_team_id"] == second["best_team_id"],
            "acceptable_jaccard": len(set(judgment["acceptable_team_ids"]) & set(second["acceptable_team_ids"]))
            / len(set(judgment["acceptable_team_ids"]) | set(second["acceptable_team_ids"])),
            "one_shot_complete": run["one_shot_complete"],
        }
        for arm, ranked in ranked_by_arm.items():
            if ranked is not None:
                record[arm] = _score_user(ranked, judgment)
        records.append(record)

    real = [r for r in records if r["origin"] == "real"]
    synthetic = [r for r in records if r["origin"] == "synthetic"]
    agreed = [r for r in records if r["judges_agree"]]
    team_count = len(teams_raw)

    intent_seconds = [pipeline[p["id"]]["intent_seconds"] for p in profiles]
    naive_seconds = [naive[p["id"]]["seconds"] for p in profiles if p["id"] in naive]
    naive_tokens = [
        naive[p["id"]]["prompt_tokens"] + naive[p["id"]]["completion_tokens"] for p in profiles if p["id"] in naive
    ]
    missing_counter: dict[str, int] = {}
    for p in profiles:
        for field in pipeline[p["id"]]["missing_fields"]:
            missing_counter[field] = missing_counter.get(field, 0) + 1

    def share(subset: list[dict], key: str) -> str:
        hits = sum(1 for r in subset if r[key])
        low, high = wilson_interval(hits, len(subset))
        return f"{hits}/{len(subset)}명 ({hits / len(subset) * 100:.0f}%, 95% 구간 {low * 100:.0f}~{high * 100:.0f}%)"

    field_names = {"desired_roles": "희망 역할", "experience_level": "경험 수준"}

    naive_measured = [r for r in records if "naive_llm" in r]
    naive_partial_block: list[str] = []
    if len(naive_measured) < len(records):
        naive_partial_block = [
            f"> ④ LLM에 직접 묻기는 OpenAI API 크레딧이 소진돼 {len(naive_measured)}명만 측정했다. 다른 표의 ④ 수치는",
            "> 그 인원 기준이라 다른 방법과 표본이 다르다 — 같은 사용자끼리 비교한 표를 먼저 둔다.",
            "",
            f"## 결과 — ④가 측정된 {len(naive_measured)}명만 (같은 사용자끼리 비교)",
            "",
            *_render_summary_table(_summarize(naive_measured), team_count),
            "",
        ]

    lines = [
        "# 실제 사용자 기반 추천 성능 재측정",
        "",
        f"평가 대상: 사용자 {len(records)}명(실제 {len(real)}명 + 실제 프로필 형식을 따른 합성 {len(synthetic)}명), "
        f"후보 팀 {team_count}개.",
        "",
        "## 무엇을 쟀나",
        "",
        "사용자가 프로필 화면에 쓴 **원문 그대로**(장점·기술분야·키워드)를 넣고, 각 방법이 추천한 팀 순위를",
        "**원문만 읽은 채점자**의 판단과 비교했다. 채점자는 서비스의 채점 방식도, 파이프라인이 뽑아낸",
        "역할·경험 정보도 보지 못한다.",
        "",
        "- **1순위 적중**: 방법이 1위로 올린 팀이 채점자가 고른 \"가장 잘 맞는 팀\"과 같은 비율",
        "- **상위 3개 / 10개 안**: 채점자가 고른 팀이 추천 상위 3개 / 10개 안에 들어간 비율",
        "- **추천 3개 중 쓸 만한 팀**: 상위 3개 추천 중, 채점자가 \"추천해도 무리 없다\"고 본 팀의 비율",
        "- 괄호 안은 95% 신뢰구간이다. 두 방법의 구간이 크게 겹치면 그 차이는 이 표본으로는 단정하기 어렵다.",
        "",
        *naive_partial_block,
        "## 결과 — 전체 100명",
        "",
        *_render_summary_table(_summarize(records), team_count),
        "",
        f"## 결과 — 실제 사용자 {len(real)}명만",
        "",
        *_render_summary_table(_summarize(real), team_count),
        "",
        f"표본이 {len(real)}명이라 신뢰구간이 넓다 — 방향을 보는 용도로만 읽는다.",
        "",
        f"## 결과 — 합성 사용자 {len(synthetic)}명만",
        "",
        *_render_summary_table(_summarize(synthetic), team_count),
        "",
        f"## 채점이 흔들리지 않는 사용자만 ({len(agreed)}명)",
        "",
        "팀 순서를 바꿔 두 번 채점했을 때 \"가장 잘 맞는 팀\"이 똑같이 나온 사용자만 모았다. 정답 자체가",
        "애매한 사용자를 뺀 결과라, 방법 간 차이가 더 순수하게 드러난다.",
        "",
        *_render_summary_table(_summarize(agreed), team_count),
        "",
        "## 채점은 얼마나 믿을 만한가",
        "",
        f"- 팀 순서를 바꿔 두 번 채점했을 때 가장 잘 맞는 팀이 같게 나온 비율: {share(records, 'judges_agree')}",
        f"- 두 번의 \"추천해도 무리 없는 팀\" 목록이 겹치는 정도(자카드 평균): "
        f"{sum(r['acceptable_jaccard'] for r in records) / len(records):.2f}",
        "- 채점자도 LLM(`" + get_settings().openai_judge_model + "`)이다. 사람이 판단한 정답이 아니므로,",
        "  실제 사용자 11명은 본인에게 채점자가 고른 팀을 확인받는 게 다음 단계다.",
        "",
        "## 에이전트 파이프라인 지표",
        "",
        f"- **프로필 글만으로 바로 추천까지 간 사용자**: {share(records, 'one_shot_complete')}",
        f"  - 실제 사용자: {share(real, 'one_shot_complete')}",
        "  - 나머지는 서비스에서 챗봇이 추가 질문을 하게 된다. 가장 많이 빠진 항목: "
        + (
            ", ".join(f"{field_names.get(k, k)} {v}명" for k, v in sorted(missing_counter.items(), key=lambda kv: -kv[1]))
            or "없음"
        ),
        "  - 이 평가에서는 추가 질문 답을 지어내지 않고, 글에서 뽑힌 정보만으로 순위를 냈다(서비스보다 불리한 조건).",
        f"- **대화 1회당 의도 파악 시간**(LLM 2회 — 구조화 추출 + 답변 문장): "
        f"중앙값 {_median_p90(intent_seconds)[0]:.1f}초, 느린 쪽 10% 경계 {_median_p90(intent_seconds)[1]:.1f}초",
        "",
        "## 추천 한 번에 걸리는 시간과 비용",
        "",
        "| 방법 | 추천 1회 시간 (중앙값) | 추천 1회당 LLM 호출 |",
        "|---|---|---|",
        f"| {ARM_LABELS['embedding_only']} | {_median_p90(ranking_ms['embedding_only'])[0]:.1f}ms | 0회 |",
        f"| {ARM_LABELS['pipeline']} | {_median_p90(ranking_ms['pipeline'])[0]:.1f}ms | 0회 *(의도 파악은 대화당 1번)* |",
        f"| {ARM_LABELS['naive_llm']} | {_median_p90(naive_seconds)[0] * 1000:.0f}ms | 1회 (평균 {sum(naive_tokens) / max(len(naive_tokens), 1):,.0f}토큰) |",
        f"| {ARM_LABELS['legacy_rule']} | {_median_p90(ranking_ms['legacy_rule'])[0]:.1f}ms | 0회 |",
        "",
        f"기존 룰베이스는 {legacy_zero_users}명에게서 희망직무 키워드가 모집글과 하나도 안 겹쳐 모든 팀이 0점이었다",
        "— 이 사용자들에게는 사실상 무작위 순서가 추천된다(원본 시스템도 그렇게 동작한다).",
        "",
        "## 실제 사용자별 1순위 적중",
        "",
        "| 사용자 | 채점 일치 | ② 파이프라인 | ④ LLM 직접 | ⑤ 룰베이스 | ① 의미만 |",
        "|---|---|---|---|---|---|",
    ]
    for record in real:
        mark = lambda arm: "—" if arm not in record else ("O" if record[arm]["top1"] else "·")  # noqa: E731
        lines.append(
            f"| {record['id']} | {'O' if record['judges_agree'] else '흔들림'} | {mark('pipeline')} | "
            f"{mark('naive_llm')} | {mark('legacy_rule')} | {mark('embedding_only')} |"
        )

    lines += [
        "",
        "## 방법론 노트",
        "",
        "- 실제 사용자 11명: 프로필 화면 캡처를 판독한 원문. 합성 89명: `gpt-5.6-terra`가 실제 11명의",
        "  쓰는 방식(길이 편차, 빈 키워드 칸, 제각각인 기술분야 형식, 역할을 명시하지 않는 서술)을 따라",
        "  만들었다. 실제 표본이 개발·데이터 계열에 치우쳐 있어, 팀 50개가 모집하는 디자인·기획·마케팅 등을",
        "  반영하려고 합성 사용자는 비개발 계열을 약 40% 섞었다(`scripts/generate_realistic_user_profiles.py`).",
        "- 후보 팀 50개는 이전 평가의 `gpt-5.6-terra` 생성 팀을 그대로 썼다.",
        "- ⑤ 기존 룰베이스는 백엔드 `EventMatchingService.matchInterestJob`을 동작 그대로 옮겼다. 프로필 화면에",
        "  희망직무 칸이 없어 키워드를 희망직무로 쓰고, 키워드가 없으면 기술분야를 잘라 썼다 — 원본에 가장",
        "  유리한 가정이다(`app/evaluation/legacy_rule_matching.py`).",
        "- ④는 원문과 팀 목록을 `" + get_settings().openai_llm_model + "`에 그대로 주고 순위를 받았다.",
        "- 이전 평가의 NDCG 0.98은 정답 프롬프트가 서비스 채점 기준을 그대로 알려준 탓에 생긴 자기 확인이었다.",
        "  이번 채점 프롬프트는 `prompts/eval_ground_truth_blind.txt`.",
        "- 재현: `generate_realistic_user_profiles.py` → `run_realistic_eval.py`. 원문이 담긴 캐시는 커밋하지 않는다.",
    ]

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))
    print(f"\n리포트 저장: {REPORT_PATH.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    asyncio.run(main())
