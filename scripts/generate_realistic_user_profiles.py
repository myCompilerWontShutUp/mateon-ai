"""실제 사용자 11명의 프로필을 기준으로 평가용 사용자 100명을 만든다.

- 실제 11명은 판독 결과(`data/real_user_profiles.json`) 그대로 넣는다.
- 나머지 89명은 `gpt-5.6-terra`가 실제 11명의 **쓰는 방식**(길이 편차, 비어 있는 키워드 칸,
  제각각인 기술분야 형식, 역할을 명시하지 않는 서술, 가끔 섞인 오탈자)을 따라 만든다. 사실 관계는
  베끼지 않게 지시한다(`prompts/eval_realistic_user_generation.txt`).

분야 비중: 실제 표본 11명은 거의 전부 개발·데이터·AI·인프라 계열이다. 평가에 쓰는 팀 50개는
디자인·기획·마케팅·콘텐츠 등도 절반 가까이 모집하므로, 합성 89명은 개발 계열 약 60% / 나머지
약 40%로 섞었다. 리포트는 실제 11명과 합성 89명의 결과를 따로도 보여준다.

출력: `data/eval_realistic_profiles.json` — 실제 사용자 글이 섞여 있어 `.gitignore` 대상이다.

사용법:
    uv run python scripts/generate_realistic_user_profiles.py          # 캐시가 있으면 건너뜀
    uv run python scripts/generate_realistic_user_profiles.py --force  # 다시 생성
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.core.prompts import load_prompt  # noqa: E402
from app.evaluation.schemas import RealisticUserProfile, RealisticUserProfileBatch  # noqa: E402
from app.openai_client.extraction import extract_structured  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REAL_PATH = DATA_DIR / "real_user_profiles.json"
OUTPUT_PATH = DATA_DIR / "eval_realistic_profiles.json"

TARGET_TOTAL = 100
_GENERATION_MODEL = "gpt-5.6-terra"
_PROMPT = load_prompt("eval_realistic_user_generation")

# (묶음 크기, 분야 비중) — 합계 89. 묶음마다 비개발 계열을 다르게 둬서 전체가 한쪽으로 쏠리지 않게 한다.
_BATCHES = [
    (30, "개발·데이터·AI·인프라 계열 18명, 디자인·기획/PM 계열 12명"),
    (30, "개발·데이터·AI·인프라 계열 18명, 마케팅·콘텐츠/영상·리서치·사업/운영 계열 12명"),
    (29, "개발·데이터·AI·인프라 계열 17명, 디자인·기획/PM·마케팅·콘텐츠 계열을 섞어 12명"),
]
_MAX_ATTEMPTS_PER_BATCH = 4


def _format_reference(profile: dict) -> str:
    truncated = set(profile.get("truncated", []))
    strengths = profile["strengths"] + (" …(이하 캡처에서 잘림)" if "strengths" in truncated else "")
    tech_field = profile["tech_field"] + (" …(이하 캡처에서 잘림)" if "tech_field" in truncated else "")
    keywords = profile.get("keywords") or []
    keyword_text = " ".join(f"#{k}" for k in keywords) if keywords else "(비어 있음)"
    return f"장점: {strengths}\n기술분야: {tech_field}\n키워드: {keyword_text}"


async def _generate(size: int, focus: str, reference: str, openings: list[str]) -> list[RealisticUserProfile]:
    collected: list[RealisticUserProfile] = []
    for attempt in range(1, _MAX_ATTEMPTS_PER_BATCH + 1):
        remaining = size - len(collected)
        if remaining <= 0:
            break
        avoid = "\n".join(f"- {text}" for text in openings[-120:]) or "(없음)"
        user_message = (
            f"[실제 사용자 프로필 표본]\n{reference}\n\n"
            f"[이번 묶음] 정확히 {remaining}개를 만든다. 분야 비중: {focus} (남은 개수에 맞게 비율을 유지).\n\n"
            f"[이미 만든 프로필의 첫머리 — 이와 겹치지 않게]\n{avoid}"
        )
        batch = await extract_structured(
            messages=[{"role": "system", "content": _PROMPT}, {"role": "user", "content": user_message}],
            response_model=RealisticUserProfileBatch,
            model=_GENERATION_MODEL,
        )
        new_profiles = batch.profiles[:remaining]
        collected.extend(new_profiles)
        openings.extend(p.strengths[:40].replace("\n", " ") for p in new_profiles)
        print(f"  시도 {attempt}: {len(new_profiles)}개 받음 (누적 {len(collected)}/{size})")
    if len(collected) < size:
        raise SystemExit(f"{size}개를 채우지 못했다({len(collected)}개) — 다시 실행하세요.")
    return collected


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="캐시가 있어도 다시 생성")
    args = parser.parse_args()

    if OUTPUT_PATH.exists() and not args.force:
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        print(f"캐시 재사용: {OUTPUT_PATH.name} ({len(existing['profiles'])}명) — 다시 만들려면 --force")
        return

    real = json.loads(REAL_PATH.read_text(encoding="utf-8"))["profiles"]
    reference = "\n\n".join(f"[표본 {i}]\n{_format_reference(p)}" for i, p in enumerate(real, start=1))

    profiles = [
        {
            "id": p["id"],
            "origin": "real",
            "strengths": p["strengths"],
            "tech_field": p["tech_field"],
            "keywords": p.get("keywords") or [],
        }
        for p in real
    ]

    openings: list[str] = []
    synthetic_count = 0
    for size, focus in _BATCHES:
        print(f"합성 묶음 생성: {size}명 ({focus})")
        for generated in await _generate(size, focus, reference, openings):
            synthetic_count += 1
            profiles.append(
                {
                    "id": f"syn_{synthetic_count}",
                    "origin": "synthetic",
                    "strengths": generated.strengths,
                    "tech_field": generated.tech_field,
                    "keywords": [k.strip().lstrip("#") for k in generated.keywords if k.strip().lstrip("#")],
                }
            )

    if len(profiles) != TARGET_TOTAL:
        raise SystemExit(f"총 {len(profiles)}명 — {TARGET_TOTAL}명이 아니다")

    OUTPUT_PATH.write_text(
        json.dumps({"generation_model": _GENERATION_MODEL, "profiles": profiles}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    empty_keywords = sum(1 for p in profiles if not p["keywords"])
    short = sum(1 for p in profiles if len(p["strengths"]) + len(p["tech_field"]) < 80)
    print(f"\n저장: {OUTPUT_PATH.name} — 실제 {len(real)}명 + 합성 {synthetic_count}명")
    print(f"키워드 빈칸 {empty_keywords}명, 짧은 프로필(장점+기술분야 80자 미만) {short}명")


if __name__ == "__main__":
    asyncio.run(main())
