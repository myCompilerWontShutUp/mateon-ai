from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@lru_cache
def load_prompt(name: str) -> str:
    raw = (_PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
    # '#'로 시작하는 줄은 메타데이터 주석이다 — LLM에 실제로 보내는 프롬프트에는 포함시키지 않는다.
    lines = [line for line in raw.splitlines() if not line.lstrip().startswith("#")]
    return "\n".join(lines).strip()
