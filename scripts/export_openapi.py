"""BE와 공유하는 계약 스펙(docs/openapi.json)을 현재 코드에서 다시 만든다.

운영 서버는 /docs·/openapi.json을 노출하지 않는다(API_DOCS_ENABLED 기본값 false). 그래서 계약의 기준은
이 스크립트로 만든 파일이다 — 요청/응답 스키마나 enum(역할 코드 등)을 바꾸면 다시 실행한다.

사용 예:
    uv run python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 기본 cp949 대응

from app.main import create_app  # noqa: E402

OUTPUT_PATH = ROOT / "docs" / "openapi.json"


def main() -> None:
    spec = create_app().openapi()
    OUTPUT_PATH.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"생성 완료: {OUTPUT_PATH} (경로 {len(spec['paths'])}개)")


if __name__ == "__main__":
    main()
