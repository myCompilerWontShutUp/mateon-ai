from pydantic import BaseModel

from app.schemas.common import MatchDirection
from app.schemas.proposal import SelectionContext


class SelectionEventRequest(BaseModel):
    direction: MatchDirection
    # 예전에는 /proposals/*의 team_id(USER_TO_TEAM)/user_id(TEAM_TO_USER)를 "선택된 후보"로
    # 암묵적으로 재사용했다 — 엔드포인트가 분리되면서 그 컨텍스트가 없어져 명시 필드로 뺐다.
    selected_candidate_id: int
    selection_context: SelectionContext


class SelectionEventResponse(BaseModel):
    # fire-and-forget이라 실제 Supabase 기록 성공 여부와 무관하게 항상 True — 응답 경로를
    # 막지 않는다는 기존 계약을 그대로 유지한다(CLAUDE.md 참고). 기록 실패는 서버 로그에만 남는다.
    accepted: bool = True
