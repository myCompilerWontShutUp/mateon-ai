"""측정 결과를 터미널에 한 번에 뿌린다 — 리포트 파일을 열어보지 않고 수치만 빠르게 볼 때.

계산을 다시 하지 않는다. `run_eval.py` / `run_eval_on_llm_pool.py` / `run_cf_demo_eval.py`가
이미 만들어둔 리포트 마크다운을 읽어 출력할 뿐이라, 항상 **마지막 평가 실행 결과**와 일치한다
(수치를 이 스크립트에 적어두지 않는 이유 — 그러면 리포트와 어긋날 수 있다).

사용법:
    uv run python scripts/show_eval_summary.py
"""

import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# cmd 창은 기본 코드페이지가 cp949라, 파이썬이 UTF-8로 내보내도 콘솔이 cp949로 해석해
# 한글이 깨진다. 사용자가 매번 `chcp 65001`을 치지 않아도 되도록 여기서 직접 바꾼다
# (실패해도 무시 — 파이프로 넘길 때나 다른 터미널에서는 애초에 필요 없다).
if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
MONITORING = ROOT / "docs" / "monitoring"

DETERMINISTIC = MONITORING / "hit-at-10-eval-report.md"
LLM_POOL = MONITORING / "hit-at-10-eval-report-llm-pool.md"
CF_DEMO = MONITORING / "cf-demo-eval-report.md"


def _width(text: str) -> int:
    """한글은 터미널에서 두 칸을 차지한다 — 열을 맞추려면 글자 수가 아니라 이 폭을 써야 한다."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, target: int) -> str:
    return text + " " * max(1, target - _width(text))


def _clean(text: str) -> str:
    return re.sub(r"[*`]", "", text).strip()


def _short(name: str) -> str:
    """표에 적힌 긴 이름에서 괄호 설명·군더더기를 떼어 한 줄에 들어가게 만든다."""
    text = re.sub(r"\s*[(（].*?[)）]", "", _clean(name)).strip()
    return text.removesuffix(" 관심층").removesuffix("관심층").strip()


def _short_field(pair: str) -> str:
    """DESIGN_PHOTO_ART_VIDEO → POLITICS_SOCIETY_LAW 처럼 긴 코드 쌍을 앞 토막만 남긴다."""
    return " → ".join(part.strip().split("_")[0] for part in _clean(pair).split("→"))


def _rows_after(path: Path, heading: str) -> list[list[str]]:
    """소제목(또는 표의 헤더 행) 다음에 나오는 마크다운 표의 데이터 행을 돌려준다."""
    if not path.exists():
        return []

    heading_is_header_row = heading.lstrip().startswith("|")
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip().startswith(heading))
    except StopIteration:
        return []

    rows: list[list[str]] = []
    seen_table = False
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("|"):
            seen_table = True
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):  # 구분선
                continue
            rows.append(cells)
        elif seen_table and stripped:
            break

    # 검색어로 헤더 행 자체를 넘겼다면 헤더는 이미 소비된 상태다.
    return rows if heading_is_header_row else rows[1:]


def _cost(path: Path) -> str:
    if not path.exists():
        return "리포트 없음"
    text = path.read_text(encoding="utf-8")
    tokens = re.search(r"총 ([\d,]+) ?토큰", text)
    seconds = re.search(r"평균 응답 시간:\s*([\d.]+)초", text)
    cost = re.search(r"\$([\d.]+)", text)
    return "  ".join(
        [
            _pad(f"{seconds.group(1)}초/호출" if seconds else "-", 12),
            _pad(f"{int(tokens.group(1).replace(',', '')):,}토큰" if tokens else "-", 12),
            f"${cost.group(1)}" if cost else "-",
        ]
    )


def _arms(path: Path, label: str) -> None:
    print(f"  {label}")
    rows = _rows_after(path, "## 전체 평균")
    if not rows:
        print(f"    (리포트 없음: {path.relative_to(ROOT).as_posix()})")
        return
    for cells in rows:
        name = _pad(_short(cells[0]), 30)
        hit, ndcg, _pref_ndcg, recovery = (_clean(c) for c in cells[1:5])
        print(f"    {name}{hit} / {ndcg} / {recovery}")


def main() -> None:
    print("Mate-On AI 추천 엔진 — 측정 결과")

    print("\n[1] 추천 방법론 4종        Hit@10 / NDCG@10 / 선호회복률")
    _arms(DETERMINISTIC, "평가셋 A · 결정론적 생성 (유저 50 / 팀 50)")
    _arms(LLM_POOL, "평가셋 B · gpt-5.6-terra 생성 (유저 50 / 팀 50)")

    print("\n[2] 대조군 비용            LLM 직접 순위, 50건 기준")
    print(f"  {_pad('평가셋 A', 30)}{_cost(DETERMINISTIC)}")
    print(f"  {_pad('평가셋 B', 30)}{_cost(LLM_POOL)}")

    print("\n[3] CF 교차 분야 발견율    콘텐츠 기반 -> CF 단독")
    for cells in _rows_after(CF_DEMO, "| 집단 | 본 분야"):
        group, fields, content, cf = (_clean(c) for c in cells[:4])
        print(f"  {_pad(_short(group), 20)}{_pad(_short_field(fields), 24)}{content} -> {cf}")

    print("\n[4] CF 가중치 민감도       cf=0.05(현재) / 0.1 / 0.2 / 0.38")
    for cells in _rows_after(CF_DEMO, "## CF 가중치 민감도"):
        values = " / ".join(_clean(c) for c in cells[1:5])
        print(f"  {_pad(_short(cells[0]), 20)}{values}")

    print("\n원본: docs/monitoring/{hit-at-10-eval-report,-llm-pool,cf-demo-eval-report}.md")


if __name__ == "__main__":
    main()
