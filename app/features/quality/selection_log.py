import asyncio
import logging

from app.schemas.common import MatchDirection
from app.schemas.proposal import SelectionContext
from app.scoring.cluster import team_cluster_key, user_cluster_key
from app.supabase_client.client import get_supabase_client

logger = logging.getLogger(__name__)


def _chooser_cluster_key(direction: MatchDirection, chooser_fields: dict) -> str:
    if direction == MatchDirection.USER_TO_TEAM:
        return user_cluster_key(
            chooser_fields.get("desired_roles", []), chooser_fields.get("experience_level")
        )
    return team_cluster_key(
        chooser_fields.get("recruiting_roles", []), chooser_fields.get("contest_field")
    )


def _write_selection_event(
    direction: MatchDirection, selection_context: SelectionContext, selected_candidate_id: int
) -> None:
    row = {
        "direction": direction.value,
        "idempotency_key": selection_context.idempotency_key,
        "chooser_cluster_key": _chooser_cluster_key(direction, selection_context.chooser_fields),
        "chooser_raw_fields": selection_context.chooser_fields,
        "shown_candidates": [c.model_dump() for c in selection_context.shown_candidates],
        "selected_candidate_id": selected_candidate_id,
    }
    get_supabase_client().table("cluster_selection_events").upsert(
        row, on_conflict="idempotency_key"
    ).execute()


async def log_selection_event(
    direction: MatchDirection, selection_context: SelectionContext, selected_candidate_id: int
) -> None:
    """fire-and-forget으로 호출한다 — 응답 경로를 막지 않고, 실패해도 삼킨다."""
    try:
        await asyncio.to_thread(
            _write_selection_event, direction, selection_context, selected_candidate_id
        )
    except Exception:
        logger.exception("log_selection_event 실패 (direction=%s)", direction)
