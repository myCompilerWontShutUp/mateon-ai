from pydantic import BaseModel, Field


class TeamMember(BaseModel):
    role: str
    count: int


class TeamEmbeddingRefreshRequest(BaseModel):
    intro_text: str
    recruiting_roles: list[str]
    required_skills: list[str]
    current_members: list[TeamMember] = Field(default_factory=list)
    contest_field: str | None = None


class TeamSoftFields(BaseModel):
    activity_goal: str | None = None
    activity_style: str | None = None
    activity_intensity: str | None = None
    beginner_friendly: bool | None = None
    team_atmosphere: str | None = None
