from pydantic import BaseModel, Field

from app.schemas.contest import ContestField
from app.schemas.role_codes import RoleCode


class TeamEmbeddingRefreshRequest(BaseModel):
    # 현재 팀 구성(누가 몇 명 있는지)은 스코어링에 쓰이지 않고 임베딩 텍스트에 서술로만
    # 녹아들기 때문에 별도 필드로 구조화하지 않는다 — intro_text에 자연어로 포함시킨다
    # (예: "현재 FE 2명, Design 1명으로 구성돼 있습니다").
    intro_text: str
    # 백엔드가 아직 정규화된 코드 체계 없이 자유 텍스트로 보낸다(예: "데이터 분석", "기획") —
    # 여기서는 원문 그대로 받고, 정규화는 TeamSoftFields.recruiting_roles/contest_field에서
    # AI가 수행해 응답으로만 돌려준다(2026-08-03 변경, 아래 TeamSoftFields 주석 참고).
    recruiting_roles: list[str]
    required_skills: list[str]
    contest_field: str | None = None


class OptionalTeamFields(BaseModel):
    # 유저 쪽 OptionalUserFields와 대칭이다 — 선택 필드, missing_fields에 안 걸리고 없으면
    # "미상"으로만 렌더링된다(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 4번 참고).
    activity_time: str | None = None  # 예: "평일 저녁", "주말"


class TeamSoftFields(BaseModel):
    activity_goal: str | None = None
    activity_style: str | None = None
    activity_intensity: str | None = None
    beginner_friendly: bool | None = None
    team_atmosphere: str | None = None
    optional: OptionalTeamFields = Field(default_factory=OptionalTeamFields)
    # 유저 인텐트 쪽(UserIntentFields.desired_roles)은 이미 AI가 정규화해서 돌려주는데
    # 팀 쪽(recruiting_roles)은 백엔드가 보낸 자유 텍스트를 그대로 echo만 하고 있었다 — 같은
    # RoleCode인데 표기가 다르면(예: 유저는 "BE", 팀은 "백엔드 개발자") 역할 일치도 스코어링이
    # 항상 0이 되는 문제가 있어(app/scoring/rules.py의 overlap_ratio는 완전 문자열 일치),
    # 여기서도 같은 RoleCode enum으로 정규화해서 돌려준다(2026-08-03 추가). required_skills는
    # 열린 집합(스킬명이 무한에 가까움)이라 이 정규화 대상에서 제외했다 — 원문 그대로 echo 유지.
    recruiting_roles: list[RoleCode] = Field(default_factory=list)
    # contest_field도 마찬가지로 ContestField(공모전 이미지 추출기와 동일한 21개 코드)로
    # 정규화한다. 자율 프로젝트라 원본 contest_field가 없으면(request.contest_field is None)
    # None으로 남긴다.
    contest_field: ContestField | None = None
