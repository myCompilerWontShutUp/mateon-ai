import asyncio
import json
from pathlib import Path

from app.features.team_embedding.service import compute_team_embedding
from tests.fixtures.team_definitions import TEAM_FIXTURES

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "teams.json"


async def main() -> None:
    results = {}
    for team_id, request in TEAM_FIXTURES.items():
        result = await compute_team_embedding(request)
        results[str(team_id)] = result.model_dump()
        print(f"team {team_id}: missing_fields={result.missing_fields}")

    OUTPUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {len(results)} team fixtures to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
