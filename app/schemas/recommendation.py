from pydantic import BaseModel, Field

from app.schemas.common import EmbeddingVector


class CandidateEmbedding(BaseModel):
    candidate_id: int
    embedding_vector: EmbeddingVector
    metadata: dict = Field(default_factory=dict)


class RecommendationRequest(BaseModel):
    query_embedding_vector: EmbeddingVector
    # 방향별 룰 스코어링에 쓰는 원본 값. USER_TO_TEAM: desired_roles/skills/activity_style/
    # experience_level. TEAM_TO_USER: recruiting_roles/required_skills/activity_goal 등.
    query_metadata: dict = Field(default_factory=dict)
    candidates: list[CandidateEmbedding]


class RecommendationItem(BaseModel):
    candidate_id: int
    score: float
    label: str


class RecommendationResponse(BaseModel):
    recommendations: list[RecommendationItem]


class RecommendationReasonRequest(BaseModel):
    candidate_summary: str
    target_summary: str
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class RecommendationReason(BaseModel):
    reason: str
