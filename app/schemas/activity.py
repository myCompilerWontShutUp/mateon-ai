# 활동 방식 코드 — AI 서버·FE·BE 공통 도메인(role_codes.py와 같은 원칙, 2026-11-05).
#
# 이 필드는 "온라인으로 하는가, 오프라인으로 하는가"만 나타낸다. 이전에는 자유 텍스트라 추출 결과에
# "주 2회 스프린트 기반 협업", "책임감 있게 끝까지 완수" 같은 협업 성향 문장까지 섞여 들어왔고,
# activity_style_match_score(app/scoring/rules.py)가 문자열 완전 일치로 비교하는 탓에 실제 형식의
# 데이터 5,000쌍 중 일치가 한 건도 없었다(2026-11-05 측정, data/eval_realistic_pipeline.json ×
# data/eval_llm_pool_teams.json). 협업 성향은 자기소개·팀 소개 원문이 임베딩에 그대로 들어가므로
# 이 필드에서 다루지 않는다.
from enum import StrEnum


class ActivityStyle(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    HYBRID = "HYBRID"


ACTIVITY_STYLE_LABELS: dict[ActivityStyle, str] = {
    ActivityStyle.ONLINE: "온라인",
    ActivityStyle.OFFLINE: "오프라인",
    ActivityStyle.HYBRID: "온·오프라인 병행",
}


def activity_style_prompt_listing() -> str:
    """LLM 프롬프트에 그대로 붙여 넣을 'CODE(라벨), ...' 형식의 코드 목록."""
    return ", ".join(f"{style.value}({label})" for style, label in ACTIVITY_STYLE_LABELS.items())


def activity_style_label(value: str | None) -> str | None:
    """활동 방식 코드의 한글 라벨. 코드가 아닌 값(enum 도입 전에 저장된 자유 텍스트)은 그대로
    돌려준다 — 옛 값 때문에 화면이나 임베딩 텍스트 렌더링이 깨지지 않게."""
    if value is None:
        return None
    try:
        return ACTIVITY_STYLE_LABELS[ActivityStyle(value)]
    except ValueError:
        return value
