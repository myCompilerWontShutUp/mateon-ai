import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)

# asyncio.create_task()가 만든 Task는 참조를 들고 있지 않으면 GC로 중간에 사라질 수 있다
# (asyncio 공식 문서에서 경고하는 함정) — 완료될 때까지 이 set이 참조를 들고 있는다.
_background_tasks: set[asyncio.Task] = set()


def fire_and_forget(coro: Coroutine[Any, Any, Any]) -> None:
    """응답 경로를 막지 않는 비동기 작업을 예약한다. 실패해도 호출자에게 전파되지 않는다."""

    async def _run() -> None:
        try:
            await coro
        except Exception:
            logger.exception("fire_and_forget 작업 실패")

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
