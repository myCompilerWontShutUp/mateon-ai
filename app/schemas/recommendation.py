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
    # 유사도 + 메타데이터 컴포넌트별 점수(similarity/role_match/deficit_fit/beginner_fit/
    # activity_style_match). 백엔드가 사용자가 이 후보를 선택했을 때 /proposals/*의
    # selection_context.shown_candidates로 그대로 되돌려 보내는 용도 — 클러스터별 가중치
    # 보정의 입력 데이터가 된다(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 참고).
    component_scores: dict[str, float]


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
