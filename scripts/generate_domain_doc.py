"""docs/domain-enums.md(BE·FE 공유용 도메인 코드 표)를 코드에서 다시 생성한다.

역할·활동 방식·공모전 코드를 바꾼 뒤 실행한다. 생성하지 않으면 tests/test_domain_enums.py가
실패한다. OpenAI·Supabase 호출 없음.

사용법:
    uv run python scripts/generate_domain_doc.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 기본 cp949 대응

from app.schemas.domain_doc import DOC_PATH, render_domain_doc  # noqa: E402


def main() -> None:
    DOC_PATH.write_text(render_domain_doc(), encoding="utf-8", newline="\n")
    print(f"생성 완료: {DOC_PATH}")


if __name__ == "__main__":
    main()
