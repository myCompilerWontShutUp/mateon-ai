from pydantic import BaseModel


class ProposalTextFields(BaseModel):
    # USER_TO_TEAM: summary=제안 요약, message=지원 동기. TEAM_TO_USER: summary=팀 소개 요약, message=스카우트 메시지.
    summary: str
    message: str


class RecommendationReasonText(BaseModel):
    reason: str
