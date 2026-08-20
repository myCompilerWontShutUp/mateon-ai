"""`cluster_weight_config`(Supabase) 읽기/쓰기 — 1번 항목(오프라인 클러스터 가중치 재계산
배치)의 저장소 계층. 재계산 자체(`app/scoring/cluster_weights.py`)와 분리해뒀다 — 저 모듈은
순수 함수라 Supabase 없이도 단위 테스트가 가능해야 하기 때문이다.

`weight_value` 컬럼에는 최종 가중치 숫자가 아니라 `adjust_weights()`가 받는 **lift** 값을
그대로 저장한다(양수만, `compute_weight_lifts()`가 만드는 값). `weight_type`은 스키마상
'override'/'bonus' 둘 중 하나만 허용되는데, 이 값들은 기존 WEIGHTS 컴포넌트의 상대 비중을
조정(override)하는 용도라 'override'로 통일한다.
"""

import logging

from app.supabase_client.client import get_supabase_client

logger = logging.getLogger(__name__)

TABLE = "cluster_weight_config"


def read_cluster_lifts() -> dict[str, dict[str, float]]:
    """활성(is_active) 행을 전부 읽어 {cluster_key: {component: lift}}로 재구성한다.

    라이브 추천 요청 경로에서 호출되므로, Supabase 조회가 실패해도 예외를 밖으로 던지지
    않는다 — 실패하면 빈 dict를 돌려줘서 `adjust_weights()`가 기본 WEIGHTS를 그대로 쓰게
    만든다(보정 없음으로 안전하게 후퇴, 사용자 응답 자체는 절대 막지 않는다).
    """
    try:
        client = get_supabase_client()
        res = (
            client.table(TABLE)
            .select("cluster_key,component,weight_value")
            .eq("is_active", True)
            .execute()
        )
    except Exception:
        logger.exception("cluster_weight_config 조회 실패 — 보정 없이 기본 WEIGHTS로 진행")
        return {}

    result: dict[str, dict[str, float]] = {}
    for row in res.data:
        result.setdefault(row["cluster_key"], {})[row["component"]] = row["weight_value"]
    return result


def write_cluster_lifts(lifts: dict[str, dict[str, float]], source: str) -> None:
    """오프라인 배치 전용(라이브 요청 경로에서는 호출하지 않는다). 클러스터·컴포넌트별로 새
    버전을 기록하고, 기존 활성 행은 지우지 않고 비활성화만 한다 — 재조정이 오히려 성능을
    악화시켰을 때 이전 버전의 is_active를 다시 true로 돌리는 것만으로 롤백할 수 있다."""
    client = get_supabase_client()
    for cluster_key, components in lifts.items():
        for component, lift in components.items():
            existing = (
                client.table(TABLE)
                .select("id,version")
                .eq("cluster_key", cluster_key)
                .eq("component", component)
                .eq("is_active", True)
                .execute()
            )
            next_version = 1
            if existing.data:
                next_version = existing.data[0]["version"] + 1
                client.table(TABLE).update({"is_active": False}).eq(
                    "id", existing.data[0]["id"]
                ).execute()

            client.table(TABLE).insert(
                {
                    "cluster_key": cluster_key,
                    "component": component,
                    "weight_type": "override",
                    "weight_value": lift,
                    "source": source,
                    "version": next_version,
                    "is_active": True,
                }
            ).execute()
            logger.info(
                "cluster_weight_config 갱신: %s/%s -> lift=%.4f (v%d, source=%s)",
                cluster_key,
                component,
                lift,
                next_version,
                source,
            )
