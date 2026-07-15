from pydantic import BaseModel

from app.schemas.common import MatchDirection


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
