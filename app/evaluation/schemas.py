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


class RealisticUserProfile(BaseModel):
    """실제 서비스 프로필 입력 화면(장점/기술분야/키워드)과 같은 형식의 사용자 프로필.

    `GeneratedUserProfile`과 달리 희망 역할·경험 수준 같은 구조화 필드가 없다 — 실제 화면에 그런
    칸이 없어서다. 구조화는 평가 대상인 에이전트 파이프라인(`/intents/extract`)이 직접 해야 한다.
    """

    strengths: str
    tech_field: str
    keywords: list[str] = Field(default_factory=list, max_length=12)


class RealisticUserProfileBatch(BaseModel):
    profiles: list[RealisticUserProfile] = Field(min_length=1, max_length=40)


class BlindGroundTruthJudgment(BaseModel):
    """원문만 보고 내린 정답 판단 — 서비스의 채점 기준이나 추출 결과를 보여주지 않는다
    (`GroundTruthLabel`은 프롬프트에 서비스 채점 기준을 그대로 알려줘 자기 확인이 됐다)."""

    best_team_id: int
    acceptable_team_ids: list[int]
    rationale: str
