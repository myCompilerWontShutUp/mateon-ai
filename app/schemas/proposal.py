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
    portfolio_role_fit_score: float | None = None

    summary: str
    message: str
