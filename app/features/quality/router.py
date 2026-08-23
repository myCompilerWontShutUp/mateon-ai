from fastapi import APIRouter, Depends

from app.api.internal_auth import require_internal_secret
from app.core.background import fire_and_forget
from app.features.quality.selection_log import log_selection_event
from app.schemas.selection_event import SelectionEventRequest, SelectionEventResponse

router = APIRouter(tags=["quality"], dependencies=[Depends(require_internal_secret)])


@router.post(
    "/selection-events",
    summary="선택 이벤트 로깅 (클러스터별 가중치 보정용, /proposals/*와 분리됨)",
)
async def log_selection_event_endpoint(request: SelectionEventRequest) -> SelectionEventResponse:
    fire_and_forget(
        log_selection_event(request.direction, request.selection_context, request.selected_candidate_id)
    )
    return SelectionEventResponse()
