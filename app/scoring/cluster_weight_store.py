"""`cluster_weight_config`(Supabase) 읽기/쓰기 — 1번 항목(오프라인 클러스터 가중치 재계산
배치)의 저장소 계층. 재계산 자체(`app/scoring/cluster_weights.py`)와 분리해뒀다 — 저 모듈은
순수 함수라 Supabase 없이도 단위 테스트가 가능해야 하기 때문이다.

`weight_value` 컬럼에는 최종 가중치 숫자가 아니라 `adjust_weights()`가 받는 **lift** 값을
그대로 저장한다(양수만, `compute_weight_lifts()`가 만드는 값). `weight_type`은 스키마상
'override'/'bonus' 둘 중 하나만 허용되는데, 이 값들은 기존 WEIGHTS 컴포넌트의 상대 비중을
조정(override)하는 용도라 'override'로 통일한다. `cluster_key`에는 방향을 붙인 키
(`app/scoring/cluster.py`의 `lift_key`, 예: "USER_TO_TEAM|BE:beginner")를 쓴다.

기록·롤백·합성 데이터 차단은 `event_cooccurrence`와 같은 규칙이다(app/supabase_client/snapshots.py).
라이브 읽기는 추천 요청마다 표를 다시 읽지 않게 Settings.config_cache_seconds 동안 캐시하고, 조회가
실패하면 직전 값(없으면 빈 dict → 기본 WEIGHTS)을 LIVE_READ_FAILURE_BACKOFF_SECONDS 동안 다시 쓴다
— 장애가 이어지는 동안 요청마다 Supabase를 다시 두드리지 않기 위함이다.
"""

import logging
import threading
import time

from app.core.config import get_settings
from app.supabase_client import snapshots
from app.supabase_client.client import (
    LIVE_READ_FAILURE_BACKOFF_SECONDS,
    get_supabase_client,
    get_supabase_read_client,
)

logger = logging.getLogger(__name__)

TABLE = "cluster_weight_config"

# 테스트가 시계를 바꿀 수 있게 한 번 감싼다.
_monotonic = time.monotonic

_cache_lock = threading.Lock()
_refresh_lock = threading.Lock()
# (만료 시각, 값)
_cache: tuple[float, dict[str, dict[str, float]]] | None = None
# 직전 조회가 실패했는지 — 장애 동안 트레이스백을 한 번만 남기려고 둔다.
_failing = False


def clear_cache() -> None:
    """캐시를 비운다 — 배치가 새 버전을 쓴 직후나 테스트에서 쓴다."""
    global _cache, _failing
    with _cache_lock:
        _cache = None
        _failing = False


def _fetch_active_rows() -> list[dict]:
    client = get_supabase_read_client()
    return snapshots.fetch_pages(
        lambda start, end: client.table(TABLE)
        .select("cluster_key,component,weight_value,source")
        .eq("is_active", True)
        .order("id")
        .range(start, end)
    )


def read_cluster_lifts() -> dict[str, dict[str, float]]:
    """활성(is_active) 행을 읽어 {cluster_key: {component: lift}}로 재구성한다.

    라이브 추천 요청 경로에서 호출되므로 예외를 밖으로 던지지 않는다. 캐시가 만료된 순간 여러 요청이
    겹치면 하나만 Supabase를 읽고 나머지는 기다리지 않고 직전 값을 쓴다. 읽기 클라이언트의 타임아웃이
    짧아(app/supabase_client/client.py) Supabase가 멈춰도 한 요청이 몇 초 넘게 묶이지 않는다.
    """
    global _cache, _failing
    with _cache_lock:
        cached = _cache
    now = _monotonic()
    if cached is not None and now < cached[0]:
        return cached[1]
    last_good = cached[1] if cached is not None else {}

    if not _refresh_lock.acquire(blocking=False):
        return last_good
    try:
        try:
            rows = _fetch_active_rows()
        except Exception:
            logger.warning(
                "cluster_weight_config 조회 실패 — %d초 동안 직전 값(없으면 기본 WEIGHTS)으로 진행",
                LIVE_READ_FAILURE_BACKOFF_SECONDS,
                exc_info=not _failing,
            )
            with _cache_lock:
                _failing = True
                _cache = (now + LIVE_READ_FAILURE_BACKOFF_SECONDS, last_good)
            return last_good

        result: dict[str, dict[str, float]] = {}
        skipped = 0
        for row in rows:
            if snapshots.is_synthetic_source(row.get("source")):
                skipped += 1
                continue
            result.setdefault(row["cluster_key"], {})[row["component"]] = row["weight_value"]
        if skipped:
            logger.warning("cluster_weight_config의 합성 데이터 활성 행 %d개를 무시했다", skipped)

        with _cache_lock:
            _failing = False
            _cache = (now + get_settings().config_cache_seconds, result)
        return result
    finally:
        _refresh_lock.release()


def write_cluster_lifts(lifts: dict[str, dict[str, float]], source: str) -> int:
    """오프라인 배치 전용(라이브 요청 경로에서는 호출하지 않는다). lifts 전체를 새 버전 하나로
    기록·전환하고 그 버전 번호를 돌려준다. 합성 데이터 출처나 빈 lifts는 거부한다."""
    rows = [
        {
            "cluster_key": cluster_key,
            "component": component,
            "weight_type": "override",
            "weight_value": lift,
            "source": source,
        }
        for cluster_key, components in lifts.items()
        for component, lift in components.items()
    ]
    version = snapshots.write_snapshot(get_supabase_client(), TABLE, rows)
    clear_cache()
    logger.info("cluster_weight_config v%d 기록: %d행 (source=%s)", version, len(rows), source)
    return version


def activate_version(version: int) -> None:
    """지정한 버전만 켜고 나머지는 끈다 — 재조정이 성능을 악화시켰을 때의 롤백용."""
    snapshots.activate_version(get_supabase_client(), TABLE, version)
    clear_cache()
    logger.info("cluster_weight_config 버전 %d로 전환", version)


def deactivate_all() -> int:
    """활성 보정값을 전부 끈다(기본 WEIGHTS로 돌아간다). 끈 행 수를 돌려준다."""
    count = snapshots.deactivate_all(get_supabase_client(), TABLE)
    clear_cache()
    logger.info("cluster_weight_config 활성 행 %d개를 껐다", count)
    return count
