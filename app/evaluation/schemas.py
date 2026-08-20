from pydantic import BaseModel, Field

from app.schemas.contest import ContestField
from app.schemas.role_codes import ExperienceLevel, RoleCode


class GroundTruthLabel(BaseModel):
    relevant_team_ids: list[int]
    rationale: str


class NaiveRankingResult(BaseModel):
    ranked_team_ids: list[int]


class GeneratedTeamProfile(BaseModel):
    """LLM(gpt-5.6-terra)이 생성한 평가용 가상 팀 프로필 — `tests/fixtures/eval_definitions.py`의
    결정론적 조합 생성 대신, 더 현실적이고 다양한 표현을 얻기 위한 대안 소스. 필드는
    `TeamEmbeddingRefreshRequest`/`TeamSoftFields`와 1:1로 대응해 그대로 조립할 수 있게 맞췄다."""

    intro_text: str
    recruiting_roles: list[RoleCode] = Field(min_length=1, max_length=2)
    required_skills: list[str] = Field(min_length=1, max_length=4)
    contest_field: ContestField | None = None
    activity_goal: str
    activity_style: str
    activity_intensity: str
    beginner_friendly: bool
    team_atmosphere: str


class GeneratedTeamPool(BaseModel):
    teams: list[GeneratedTeamProfile] = Field(min_length=50, max_length=50)


class GeneratedUserProfile(BaseModel):
    """LLM(gpt-5.6-terra)이 생성한 평가용 가상 유저 프로필 — `UserIntentFields`와 1:1 대응."""

    conversation_text: str
    desired_roles: list[RoleCode] = Field(min_length=1, max_length=2)
    skills: list[str] = Field(min_length=0, max_length=3)
    interests: list[str] = Field(min_length=1, max_length=3)
    activity_goal: str
    activity_style: str
    experience_level: ExperienceLevel


class GeneratedUserPool(BaseModel):
    users: list[GeneratedUserProfile] = Field(min_length=50, max_length=50)
