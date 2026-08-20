"""Hit@10 평가용 팀 50개·유저 50개 구조화 필드를 `tests/fixtures/eval_definitions.py`의 결정론적
조합 생성 대신 실제 OpenAI API(gpt-5.6-terra)로 생성한다 — 더 현실적이고 다양한 문장/조합을 얻기
위한 대안 소스다(2026-08-20, 사용자 요청). 결과는 `data/eval_llm_generated_definitions_cache.json`
에 캐싱하고, 이 파일은 `.gitignore`에 등록해 GitHub에는 올리지 않는다(재현 시마다 LLM 출력이
달라질 수 있는 비결정론적 데이터라, 결정론적 `eval_definitions.py`와 달리 커밋해서 공유하지
않기로 함).

`eval_definitions.py`의 `generate_team_pool()`/`generate_user_pool()`을 대체하지 않는다 — 이
스크립트는 생성·캐싱까지만 하고, 이 캐시를 실제 평가 파이프라인에 연결할지는 별도 결정 사항이다.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.core.prompts import load_prompt  # noqa: E402
from app.evaluation.schemas import GeneratedTeamPool, GeneratedUserPool  # noqa: E402
from app.openai_client.extraction import extract_structured  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "eval_llm_generated_definitions_cache.json"

_GENERATION_MODEL = "gpt-5.6-terra"
_TEAM_PROMPT = load_prompt("eval_team_pool_generation")
_USER_PROMPT = load_prompt("eval_user_pool_generation")


async def _generate_teams() -> GeneratedTeamPool:
    return await extract_structured(
        messages=[
            {"role": "system", "content": _TEAM_PROMPT},
            {"role": "user", "content": "정확히 50개의 팀 프로필을 생성하세요."},
        ],
        response_model=GeneratedTeamPool,
        model=_GENERATION_MODEL,
    )


async def _generate_users() -> GeneratedUserPool:
    return await extract_structured(
        messages=[
            {"role": "system", "content": _USER_PROMPT},
            {"role": "user", "content": "정확히 50개의 유저 프로필을 생성하세요."},
        ],
        response_model=GeneratedUserPool,
        model=_GENERATION_MODEL,
    )


async def main() -> None:
    print(f"팀 50개 생성 중... (model={_GENERATION_MODEL})")
    team_pool = await _generate_teams()
    print(f"팀 {len(team_pool.teams)}개 생성 완료")

    print(f"유저 50개 생성 중... (model={_GENERATION_MODEL})")
    user_pool = await _generate_users()
    print(f"유저 {len(user_pool.users)}개 생성 완료")

    output = {
        "model": _GENERATION_MODEL,
        "teams": [t.model_dump(mode="json") for t in team_pool.teams],
        "users": [u.model_dump(mode="json") for u in user_pool.users],
    }
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(output['teams'])} teams + {len(output['users'])} users to {OUTPUT_PATH}")
    print("이 파일은 .gitignore에 등록되어 있어 커밋되지 않는다.")


if __name__ == "__main__":
    asyncio.run(main())
