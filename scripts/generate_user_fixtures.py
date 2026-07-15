import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.features.user_to_team.intent import compute_user_intent  # noqa: E402
from tests.fixtures.user_intent_definitions import USER_INTENT_FIXTURES  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "users.json"


async def main() -> None:
    results = {}
    for key, request in USER_INTENT_FIXTURES.items():
        result = await compute_user_intent(request)
        if result.missing_fields:
            raise RuntimeError(f"fixture '{key}' is incomplete: {result.missing_fields}")
        results[key] = result.model_dump()
        print(f"user {key}: extracted={result.extracted}")

    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(results)} user fixtures to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
