"""Hit@10/NDCG 평가용 정답(ground truth) 라벨을 생성한다. 사람이 50x50을 전부 손으로 라벨링하는
대신 상위 모델(OPENAI_JUDGE_MODEL, GPT-5 이상급)로 생성하고 표본만 사람이 검수한다 — 실
서비스에는 이 라벨링을 쓰지 않는다, 평가용 오프라인 작업 전용이다
(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 3번 참고).
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.core.prompts import load_prompt  # noqa: E402
from app.evaluation.schemas import GroundTruthLabel  # noqa: E402
from app.openai_client.extraction import extract_structured  # noqa: E402

TEAMS_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_teams.json"
USERS_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_users.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_ground_truth.json"

_SYSTEM_PROMPT = load_prompt("eval_ground_truth_labeling")


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


async def _label_one(user_id: str, user: dict, team_summary: str) -> GroundTruthLabel:
    settings = get_settings()
    prompt = f"[사용자 프로필]\n{_user_summary(user)}\n\n[팀 목록]\n{team_summary}"
    return await extract_structured(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_model=GroundTruthLabel,
        model=settings.openai_judge_model,
    )


async def main() -> None:
    teams = json.loads(TEAMS_PATH.read_text(encoding="utf-8"))
    users = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    team_summary = _team_summary_lines(teams)

    results = {}
    for user_id, user in sorted(users.items(), key=lambda kv: int(kv[0])):
        label = await _label_one(user_id, user, team_summary)
        results[user_id] = label.model_dump()
        print(f"user {user_id}: relevant={label.relevant_team_ids} ({len(label.relevant_team_ids)}개)")

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(results)} ground truth labels to {OUTPUT_PATH}")

    empty = [uid for uid, r in results.items() if not r["relevant_team_ids"]]
    if empty:
        print(f"주의: 정답이 0개인 사용자 {len(empty)}명 (Hit@10 계산에서 제외됨): {empty}")


if __name__ == "__main__":
    asyncio.run(main())
