"""추천 요청 경로에서 Supabase 튜닝 값(클러스터 lift, 동시발생)을 읽을 때의 공통 규칙.

두 값 모두 없어도 추천은 된다(기본 가중치, CF 0점). 그래서 조회가 오래 걸리면 기다리지 않고 빈 값으로
진행한다. 읽기 클라이언트 자체에도 짧은 타임아웃이 있지만(app/supabase_client/client.py), 페이지를 여러
번 읽으면 합쳐서 길어질 수 있어 요청 단위로 한 번 더 묶는다. 시간이 넘으면 응답은 바로 나가고, 이미 시작된
조회 스레드는 클라이언트 타임아웃까지 돌다가 끝난다.
"""

import asyncio
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

LOOKUP_TIMEOUT_SECONDS = 4.0


async def bounded_lookup(func: Callable[..., dict], *args) -> dict:
    """func(*args)를 스레드에서 실행하고, LOOKUP_TIMEOUT_SECONDS 안에 끝나지 않으면 빈 dict를 돌려준다."""
    try:
        return await asyncio.wait_for(asyncio.to_thread(func, *args), LOOKUP_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning(
            "%s가 %.0f초 안에 끝나지 않아 빈 값으로 진행",
            getattr(func, "__name__", "조회"),
            LOOKUP_TIMEOUT_SECONDS,
        )
        return {}


async def skipped_lookup() -> dict:
    """조회할 필요가 없을 때(입력 ID가 없을 때) bounded_lookup 자리에 넣는다."""
    return {}
