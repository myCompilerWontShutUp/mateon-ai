"""Hit@10/NDCG 평가(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 3번)용 팀 50개·유저 50개
fixture를 생성한다. 구조화 필드는 `tests/fixtures/eval_definitions.py`가 결정론적으로 만들고,
여기서는 템플릿 렌더링 + 실제 임베딩 API 호출만 한다(추출 파이프라인은 거치지 않음 — 평가
목적이 추출 정확도가 아니라 랭킹 방법 비교이므로).
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.features.team_embedding.template import render_team_embedding_text  # noqa: E402
from app.features.user_to_team.template import render_intent_embedding_text  # noqa: E402
from app.openai_client.embedding import embed_text  # noqa: E402
from tests.fixtures.eval_definitions import generate_team_pool, generate_user_pool  # noqa: E402

TEAMS_OUTPUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_teams.json"
USERS_OUTPUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_users.json"


async def _build_teams() -> dict:
    pool = generate_team_pool()
    results = {}
    for team_id, (request, soft_fields) in pool.items():
        embedding_text = render_team_embedding_text(request, soft_fields)
        vector = await embed_text(embedding_text)
        results[str(team_id)] = {
            "team_id": team_id,
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
        print(f"team {team_id} embedded ({len(vector)} dims)")
    return results


async def _build_users() -> dict:
    pool = generate_user_pool()
    results = {}
    for user_id, (conversation_text, fields) in pool.items():
        embedding_text = render_intent_embedding_text(conversation_text, fields)
        vector = await embed_text(embedding_text)
        results[str(user_id)] = {
            "user_id": user_id,
            "embedding_text": embedding_text,
            "embedding_vector": vector,
            "metadata": {
                "desired_roles": [r.value for r in fields.desired_roles],
                "skills": fields.skills,
                "activity_style": fields.activity_style,
                "experience_level": fields.experience_level.value if fields.experience_level else None,
            },
        }
        print(f"user {user_id} embedded ({len(vector)} dims)")
    return results


async def main() -> None:
    teams = await _build_teams()
    TEAMS_OUTPUT.write_text(json.dumps(teams, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(teams)} team fixtures to {TEAMS_OUTPUT}")

    users = await _build_users()
    USERS_OUTPUT.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(users)} user fixtures to {USERS_OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
