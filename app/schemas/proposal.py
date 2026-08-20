from pydantic import BaseModel, Field

from app.schemas.common import MatchDirection


class ShownCandidate(BaseModel):
    candidate_id: int
    total_score: float
    # /recommendations/*가 돌려준 RecommendationItem.component_scores를 그대로 echo한다.
    component_scores: dict[str, float]


class SelectionContext(BaseModel):
    # 이 요청 전용 멱등키. proposal_id가 아니다 — 이 시점엔 아직 proposal_id가 채번되기 전이라
    # (백엔드가 저장하며 채번) 그 값을 멱등키로 쓸 수 없다. 백엔드가 UUID로 새로 생성해서 보낸다.
    idempotency_key: str
    # 고르는 쪽의 클러스터 키를 만들 원본 필드. USER_TO_TEAM이면 desired_roles/experience_level,
    # TEAM_TO_USER면 recruiting_roles/contest_field — AI 서버가 클러스터 키를 직접 계산하므로
    # 백엔드는 이미 갖고 있는 정규화된 값을 그대로 실어 보내면 된다.
    chooser_fields: dict = Field(default_factory=dict)
    # 선택 시점에 화면에 보여줬던 후보 전체 (/recommendations/*의 응답을 그대로 재전송).
    shown_candidates: list[ShownCandidate] = Field(default_factory=list)


class ProposalSchema(BaseModel):
    direction: MatchDirection

    user_id: int
    team_id: int
    contest_id: int | None = None
    sender_id: int
    receiver_id: int
    # 백엔드가 소유·채번하는 식별자를 그대로 통과시킨다 (AI 서버는 저장하지 않음). 타입은 백엔드와 확인 필요.
    intent_id: int | None = None

    synergy_score: float
    # 실제 포트폴리오 데이터 소스가 생기기 전까지는 항상 None — 협업 온도와 같은 취급으로
    # 필드만 예약해둔다 (계산에서 제외한 이유는 CLAUDE.md 참고).
    portfolio_role_fit_score: float | None = None

    summary: str
    message: str


class ProposalAssemblyRequest(BaseModel):
    user_id: int
    team_id: int
    contest_id: int | None = None
    sender_id: int
    receiver_id: int
    intent_id: int | None = None

    synergy_score: float

    # LLM이 summary/message를 쓸 때 참고할 컨텍스트 — ID/점수를 대신하지 않는다.
    candidate_summary: str
    target_summary: str

    # 선택 필드 — 없으면 클러스터 선호 데이터 로깅만 건너뛰고 기존 흐름은 그대로 동작한다
    # (하위 호환 유지). 아직 Supabase에 실제로 기록하는 로직은 연결되지 않았다 — 필드만 받는
    # 단계다(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 2번 항목 참고).
    selection_context: SelectionContext | None = None
