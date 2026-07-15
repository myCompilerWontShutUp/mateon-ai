from pydantic import BaseModel


class TeamEmbeddingRefreshRequest(BaseModel):
    # 현재 팀 구성(누가 몇 명 있는지)은 스코어링에 쓰이지 않고 임베딩 텍스트에 서술로만
    # 녹아들기 때문에 별도 필드로 구조화하지 않는다 — intro_text에 자연어로 포함시킨다
    # (예: "현재 FE 2명, Design 1명으로 구성돼 있습니다").
    intro_text: str
    recruiting_roles: list[str]
    required_skills: list[str]
    contest_field: str | None = None


class TeamSoftFields(BaseModel):
    activity_goal: str | None = None
    activity_style: str | None = None
    activity_intensity: str | None = None
    beginner_friendly: bool | None = None
    team_atmosphere: str | None = None
