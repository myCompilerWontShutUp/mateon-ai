"""`event_cooccurrence`(Supabase) 읽기/쓰기 — item-to-item CF의 저장소 계층.

`cluster_weight_store.py`와 같은 패턴이다: 계산은 오프라인 배치가 하고 결과만 Supabase에
밀어넣으며, 라이브 서버는 읽기만 한다. 기록·롤백·합성 데이터 차단 규칙도 같다
(app/supabase_client/snapshots.py). 조회가 실패하면 빈 dict를 돌려준다 — CF 신호가 없으면 모든
후보의 `cf_affinity`가 0이 되어 순위가 기존과 수학적으로 동일해진다(단조 변환).

표 전체가 아니라 이번 추천에 필요한 쌍만 읽는다: target 공모전의 이웃 중, related를 주면 그 공모전과의
쌍만. 표 전체를 요청마다 읽으면 실제 데이터가 쌓였을 때 느려지고 PostgREST 행 상한에서 잘린다.
"""

import logging
import time
from collections.abc import Iterable

from app.scoring.cooccurrence import as_event_ids
from app.supabase_client import snapshots
from app.supabase_client.client import (
    LIVE_READ_FAILURE_BACKOFF_SECONDS,
    get_supabase_client,
    get_supabase_read_client,
)

logger = logging.getLogger(__name__)

TABLE = "event_cooccurrence"
# in() 필터는 URL 쿼리스트링에 실리므로 한 번에 넣는 ID 수를 제한한다.
ID_CHUNK = 200

# 테스트가 시계를 바꿀 수 있게 한 번 감싼다.
_monotonic = time.monotonic
# 조회가 실패하면 이 시각까지 Supabase를 부르지 않는다(장애 동안 요청마다 타임아웃을 기다리지 않게).
_skip_until = 0.0
_failing = False


def reset_backoff() -> None:
    """실패 후 대기 상태를 지운다 — 테스트용."""
    global _skip_until, _failing
    _skip_until = 0.0
    _failing = False


def _chunks(ids: list[int]) -> list[list[int]]:
    return [ids[start : start + ID_CHUNK] for start in range(0, len(ids), ID_CHUNK)]


def read_cooccurrence(
    target_event_ids: Iterable, related_event_ids: Iterable | None = None
) -> dict[int, dict[int, float]]:
    """target 공모전들의 이웃을 읽어 {event_id: {other_event_id: similarity}}로 돌려준다.

    대칭 행렬을 양방향으로 저장해 두었으므로 event_id = target인 행만 읽으면 그 공모전의 이웃이 전부
    나온다. related_event_ids를 주면 그 공모전과의 쌍만 읽는다 — USER_TO_TEAM은 사용자가 본 공모전만
    점수에 쓰므로 그만큼만 읽으면 된다. target(또는 주어진 related)이 비어 있으면 Supabase를 부르지
    않는다.
    """
    global _skip_until, _failing
    targets = sorted(set(as_event_ids(list(target_event_ids))))
    related = None if related_event_ids is None else sorted(set(as_event_ids(list(related_event_ids))))
    if not targets or related == []:
        return {}
    now = _monotonic()
    if now < _skip_until:
        return {}

    try:
        client = get_supabase_read_client()
        rows: list[dict] = []
        for target_chunk in _chunks(targets):
            for related_chunk in _chunks(related) if related is not None else [None]:

                def build(start: int, end: int, targets=target_chunk, neighbors=related_chunk):
                    query = (
                        client.table(TABLE)
                        .select("event_id,related_event_id,similarity,source")
                        .eq("is_active", True)
                        .in_("event_id", targets)
                    )
                    if neighbors is not None:
                        query = query.in_("related_event_id", neighbors)
                    return query.order("id").range(start, end)

                rows.extend(snapshots.fetch_pages(build))
    except Exception:
        logger.warning(
            "event_cooccurrence 조회 실패 — %d초 동안 CF 신호 없이 진행",
            LIVE_READ_FAILURE_BACKOFF_SECONDS,
            exc_info=not _failing,
        )
        _failing = True
        _skip_until = now + LIVE_READ_FAILURE_BACKOFF_SECONDS
        return {}
    _failing = False

    result: dict[int, dict[int, float]] = {}
    for row in rows:
        if snapshots.is_synthetic_source(row.get("source")):
            continue
        result.setdefault(int(row["event_id"]), {})[int(row["related_event_id"])] = row["similarity"]
    return result


def write_cooccurrence(cooccurrence: dict[int, dict[int, float]], source: str) -> int:
    """오프라인 배치 전용. 동시발생 행렬 전체를 새 버전 하나로 기록·전환하고 그 버전 번호를 돌려준다.
    이전 버전은 지우지 않으므로 activate_version()으로 롤백한다. 합성 데이터 출처나 빈 행렬은 거부한다."""
    rows = [
        {
            "event_id": event_id,
            "related_event_id": related_id,
            "similarity": similarity,
            "source": source,
        }
        for event_id, neighbors in cooccurrence.items()
        for related_id, similarity in neighbors.items()
    ]
    if not rows:
        raise ValueError("동시발생 쌍이 하나도 없다 (상호작용 데이터 부족)")
    version = snapshots.write_snapshot(get_supabase_client(), TABLE, rows)
    logger.info("event_cooccurrence v%d 기록: %d행 (source=%s)", version, len(rows), source)
    return version


def activate_version(version: int) -> None:
    """지정한 버전만 켜고 나머지는 끈다 — 롤백용."""
    snapshots.activate_version(get_supabase_client(), TABLE, version)
    logger.info("event_cooccurrence 버전 %d로 전환", version)


def deactivate_all() -> int:
    """활성 동시발생 행을 전부 끈다(CF 신호 없음 = 기존 순위). 끈 행 수를 돌려준다."""
    count = snapshots.deactivate_all(get_supabase_client(), TABLE)
    logger.info("event_cooccurrence 활성 행 %d개를 껐다", count)
    return count
