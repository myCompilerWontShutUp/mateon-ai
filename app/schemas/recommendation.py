from pydantic import BaseModel, Field


class CandidateEmbedding(BaseModel):
    candidate_id: int
    embedding_vector: list[float]
    metadata: dict = Field(default_factory=dict)


class RecommendationRequest(BaseModel):
    query_embedding_vector: list[float]
    candidates: list[CandidateEmbedding]


class RecommendationItem(BaseModel):
    candidate_id: int
    score: float
    label: str


class RecommendationResponse(BaseModel):
    recommendations: list[RecommendationItem]


class RecommendationReason(BaseModel):
    reason: str
