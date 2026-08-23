"""흥미(y축) vs 역할·스킬 일치도(x축) 사분면 차트 프로토타입 — 독립 스크립트, 실서비스
API/스키마/스코어링(WEIGHTS)은 전혀 건드리지 않는다(2026-08-23, 사용자 요청).

**배경**: `interests`(관심 분야)는 `/intents/extract` 결과에만 있고, 추천 스코어링이 보는
`query_metadata`(desired_roles/skills/activity_style/experience_level)에는 안 들어간다 —
그래서 이 프로토타입은 `eval_users.json`/`eval_teams.json`의 `embedding_text`에서
"관심 분야: "/"팀 소개: "/"공모전 분야: " 줄을 직접 파싱해 별도로 흥미 신호를 만든다.

- **x축(역할·스킬 일치도)**: 실제 프로덕션 스코어링(`app/evaluation/scoring_arms.py`의
  `production_ranking`)이 이미 계산한 `role_match`/`deficit_fit`의 평균 — 새 계산 없이 재사용.
- **y축(흥미 일치도)**: 유저의 관심 분야 텍스트와 팀의 소개/공모전 분야 텍스트를 각각
  `text-embedding-3-small`로 따로 임베딩해 cosine 유사도를 잰다 — 기존 `similarity`(스킬·역할·
  활동방식까지 다 섞인 값)와 달리 "흥미"만 격리한 신호다.

**후보 범위**: 유저 1명(`DEMO_USER_ID`)의 실제 추천 결과 **전체**(50개, 이 fixture의 팀 전부)를
대상으로 한다 — "모든 팀이 등장해야 한다"는 요청(2026-08-23)으로 top 10 컷을 없앴다. API 호출은
유저 관심사 임베딩 1회 + 팀 50개 임베딩 = 총 51회로, 여전히 비용은 무시할 수준.

**x축이 몇 개 값에 몰리는 문제**: `role_match`/`deficit_fit`는 CLAUDE.md에도 이미 기록된 대로
대부분 이산값(0/0.5/1)이라, 평균을 내도 {0, 0.25, 0.5, 0.75, 1} 같은 소수의 값에 여러 팀이
겹쳐 찍힌다 — 이건 원본 점수 자체의 해상도 한계이지 렌더링 버그가 아니다. 데이터는 원래 값
그대로 두고(정직성 유지), 화면(HTML 아티팩트) 쪽에서 겹친 점을 시각적으로만 살짝 흩뿌리는
결정론적 지터를 적용한다 — 툴팁에는 지터 전 원래 값을 그대로 보여준다.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.evaluation.scoring_arms import production_ranking  # noqa: E402
from app.openai_client.embedding import embed_text  # noqa: E402
from app.schemas.contest import CONTEST_FIELD_LABELS, ContestField  # noqa: E402
from app.scoring.similarity import cosine_similarity  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "interest_fit_demo.json"

DEMO_USER_ID = "1"


def _line_value(text: str, prefix: str) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def _field_label(code: str) -> str:
    try:
        return CONTEST_FIELD_LABELS[ContestField(code)]
    except ValueError:
        return code


async def main() -> None:
    users = json.loads((FIXTURES / "eval_users.json").read_text(encoding="utf-8"))
    teams = json.loads((FIXTURES / "eval_teams.json").read_text(encoding="utf-8"))

    user = users[DEMO_USER_ID]
    interests_text = _line_value(user["embedding_text"], "관심 분야: ")
    print(f"demo user {DEMO_USER_ID} — 관심 분야: {interests_text}")
    print(f"희망 역할/스킬: {user['metadata']['desired_roles']} / {user['metadata']['skills']}")

    ranked = production_ranking(user["embedding_vector"], user["metadata"], teams)
    top = ranked  # 후보 전체(50개) — "모든 팀이 등장해야 한다"는 요청, 2026-08-23

    interests_vec = await embed_text(f"관심 분야: {interests_text}")

    points = []
    for c in top:
        team = teams[str(c.candidate_id)]
        intro = _line_value(team["embedding_text"], "팀 소개: ")
        contest_field = team["metadata"].get("contest_field")
        domain_text = f"팀 소개: {intro}\n공모전 분야: {contest_field or '미상'}"
        domain_vec = await embed_text(domain_text)
        interest_fit = max(0.0, cosine_similarity(interests_vec, domain_vec))
        skill_fit = (c.metadata_scores["role_match"] + c.metadata_scores["deficit_fit"]) / 2

        points.append(
            {
                "team_id": c.candidate_id,
                "recruiting_roles": team["metadata"]["recruiting_roles"],
                "contest_field": contest_field,
                "contest_field_label": _field_label(contest_field) if contest_field else None,
                "intro": intro,
                "x_skill_fit": skill_fit,
                "y_interest_fit": interest_fit,
                "total_score": c.total_score,
            }
        )
        print(
            f"  team {c.candidate_id} ({team['metadata']['recruiting_roles']}): "
            f"skill_fit={skill_fit:.3f} interest_fit={interest_fit:.3f} total_score={c.total_score:.3f}"
        )

    output = {
        "user_id": DEMO_USER_ID,
        "user_desired_roles": user["metadata"]["desired_roles"],
        "user_skills": user["metadata"]["skills"],
        "user_interests": interests_text,
        "points": points,
    }
    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
