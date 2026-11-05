from functools import lru_cache

import httpx
from supabase import Client, ClientOptions, create_client

from app.core.config import get_settings

# 추천 요청 경로에서 읽는 튜닝 설정값(클러스터 lift, 동시발생) 전용 타임아웃. 기본 클라이언트는
# PostgREST 타임아웃이 120초라 Supabase가 응답 없이 멈추면 추천 요청이 그만큼 묶인다(2026-11-05
# 확인). 이 값들은 없으면 기본 가중치로 후퇴하면 되므로 짧게 끊는다.
LIVE_READ_TIMEOUT = httpx.Timeout(3.0, connect=2.0)
# 라이브 읽기가 실패하면 이 시간 동안은 다시 시도하지 않는다 — 장애가 이어지는 동안 요청마다
# 타임아웃을 기다리고 트레이스백을 남기는 일을 막는다.
LIVE_READ_FAILURE_BACKOFF_SECONDS = 30


@lru_cache
def get_supabase_client() -> Client:
    """오프라인 배치·백그라운드 기록용. 응답 경로 밖에서만 쓰므로 기본 타임아웃을 그대로 둔다."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@lru_cache
def get_supabase_read_client() -> Client:
    """추천 요청 경로의 읽기 전용 — 짧은 타임아웃(LIVE_READ_TIMEOUT)을 쓴다."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=ClientOptions(postgrest_client_timeout=LIVE_READ_TIMEOUT),
    )
