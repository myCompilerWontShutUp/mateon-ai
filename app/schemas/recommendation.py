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

    # 사용자가 북마크/지원한 공모전 임베딩의 평균(BE가 누적 평균으로 저장해두고 보낸다).
    # **USER_TO_TEAM에서만 쓰인다** — TEAM_TO_USER의 쿼리는 팀의 결핍 임베딩이라 "팀의 행동
    # 이력"이라는 개념이 성립하지 않는다(보내도 무시된다). 안 보내면 기존과 100% 동일하게
    # 동작한다(하위 호환). 협업 필터링이 아니라 개인화된 콘텐츠 기반 필터링이다 —
    # app/scoring/behavior_blend.py 참고.
    behavior_embedding_vector: EmbeddingVector | None = None
    # 위 평균을 만든 상호작용 건수. 블렌딩 비율 α를 정하는 데만 쓴다(많을수록 행동 쪽 비중↑).
    interaction_count: int = Field(default=0, ge=0)


class RecommendationItem(BaseModel):
    candidate_id: int
    score: float
    label: str
    # 유사도 + 메타데이터 컴포넌트별 점수(similarity/role_match/deficit_fit/activity_style_match/
    # beginner_fit/cf_affinity, 참고용 activity_time_match). 백엔드가 사용자가 이 후보를 선택했을 때
    # POST /selection-events의 selection_context.shown_candidates로 그대로 되돌려 보내는 용도 —
    # 클러스터별 가중치 보정의 입력 데이터가 된다.
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
