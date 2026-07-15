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
    # 점수 구성요소는 LLM 프롬프트에 그대로 문자열로 들어갈 뿐 코드가 필드별로 읽지 않으므로,
    # dict 타입을 강제할 이유가 없다 — 백엔드가 원하는 형식의 짧은 서술로 보내면 된다
    # (예: "유사도 높음, 역할 일치, 결핍 보완 낮음").
    score_context: str = ""


class RecommendationReason(BaseModel):
    reason: str
