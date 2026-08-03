# 역할/경험 수준 코드의 단일 소스. 새 도메인을 추가하고 싶으면 이 파일만 고치면 된다 —
# RoleCode에 멤버를 추가하고 ROLE_CODE_LABELS에 한글 라벨만 채우면, 이 값을 참조하는
# 프롬프트(app/features/user_to_team/extraction.py, app/features/team_embedding/extraction.py,
# app/features/user_to_team/chat_reply.py)가 자동으로 최신 목록을 LLM에 전달한다 — 프롬프트
# .txt 파일을 따로 고칠 필요가 없다(ContestField처럼 프롬프트에 코드 목록을 하드코딩해두면
# 나중에 코드를 늘릴 때마다 매번 같이 고쳐야 하는 문제를 여기서는 피한다).
#
# BE/FE/Design/PM/Data 5개는 초기 확정값이라 값(문자열)을 바꾸지 않는다 — 이미
# tests/fixtures/*.json, docs/api-contract-draft.md에 이 문자열 그대로 박혀있다. 이후 추가한
# 코드는 ContestField와 통일감을 맞추려고 대문자 스네이크로 짓는다(대소문자는 매칭 로직
# `app/scoring/rules.py`의 `overlap_ratio`가 항상 소문자로 비교하므로 스코어링에는 영향 없음
# — 순수 표기 스타일 문제).
#
# 백엔드에는 아직 이 코드에 대응하는 고정 enum이 없다(2026-08-03 mateon-backend 저장소 확인
# — Team.role/User.interestJobPrimary 등은 전부 자유 텍스트, "데이터 분석", "기획", "백엔드
# 개발자" 같은 예시만 존재). 그래서 이 목록은 백엔드 실제 코드에 남아있는 자유 텍스트 예시를
# 참고해 AI 서버가 먼저 넓게 잡고, 안정화된 뒤 백엔드와 공유해서 다시 조율하는 전제로 만들었다.
from enum import StrEnum


class RoleCode(StrEnum):
    BE = "BE"
    FE = "FE"
    DESIGN = "Design"
    PM = "PM"
    DATA = "Data"
    MARKETING = "MARKETING"  # 마케팅/홍보
    CONTENT = "CONTENT"  # 콘텐츠/영상/글쓰기
    BUSINESS = "BUSINESS"  # 사업개발/전략/운영기획
    RESEARCH = "RESEARCH"  # 리서치/기획조사 (Data와 달리 정량 분석이 아닌 정성 리서치)
    ETC = "ETC"


ROLE_CODE_LABELS: dict[RoleCode, str] = {
    RoleCode.BE: "백엔드 개발",
    RoleCode.FE: "프론트엔드 개발",
    RoleCode.DESIGN: "디자인",
    RoleCode.PM: "기획/프로젝트 관리",
    RoleCode.DATA: "데이터 분석/AI",
    RoleCode.MARKETING: "마케팅/홍보",
    RoleCode.CONTENT: "콘텐츠/영상/글쓰기",
    RoleCode.BUSINESS: "사업개발/전략/운영기획",
    RoleCode.RESEARCH: "리서치/조사",
    RoleCode.ETC: "기타",
}


class ExperienceLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


def role_code_prompt_listing() -> str:
    """LLM 프롬프트에 그대로 붙여 넣을 'CODE(라벨), ...' 형식의 코드 목록."""
    return ", ".join(f"{code.value}({label})" for code, label in ROLE_CODE_LABELS.items())


def role_code_translation_guide() -> str:
    """자연어 응답 생성용 — 'CODE→라벨' 번역 가이드 문자열."""
    return ", ".join(f"{code.value}→{label}" for code, label in ROLE_CODE_LABELS.items())
