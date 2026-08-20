"""클러스터별 가중치 보정(1번 항목)의 핵심 알고리즘 — 정식 ML 모델이 아니라 해석 가능한
휴리스틱 조정이다(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 2번: "클러스터별로 기존
WEIGHTS dict를 소폭 조정"). 입력으로 실제 `cluster_selection_events`를 기대하지만, 이 함수
자체는 이벤트가 dict 형태(원본 컬럼과 같은 키)이기만 하면 되므로 합성 데이터로도 그대로 쓸 수
있다(2번 항목 Hit@10 평가에서 실제로 이렇게 쓴다 — 실 데이터가 쌓이기 전까지의 시연용).

**2026-08-20 수정**: 처음엔 lift를 컴포넌트 점수에 더하는 방식(가산점)으로 구현했는데, 실제로
Hit@10 평가를 돌려보니 이미 점수가 높은 후보 여러 개가 동시에 1.0 상한에 부딪혀 서로 구분이
안 되면서 오히려 순위 변별력(NDCG)이 떨어지는 문제가 실측됐다 — CLAUDE.md의 원래 설계
문구("가중치를 조정")와도 어긋난 구현이었다. 그래서 점수가 아니라 **가중치 자체**를 조정하는
방식으로 다시 만들었다 — 이미 잘 분포된 컴포넌트 점수는 그대로 두고, 그 점수가 총점에 기여하는
비중만 클러스터별로 조절한다.
"""

from collections import defaultdict

# 이벤트 수가 이보다 적은 클러스터는 통계적으로 불안정하다고 보고 보정하지 않는다
# (CLAUDE.md에서 지적한 "클러스터 데이터 희소성" 리스크에 대한 최소한의 방어).
DEFAULT_MIN_EVENTS = 2


def compute_weight_lifts(
    events: list[dict],
    components: list[str],
    min_events: int = DEFAULT_MIN_EVENTS,
) -> dict[str, dict[str, float]]:
    """클러스터별로 "선택된 후보"와 "보여진 후보 전체 평균"의 컴포넌트별 점수 차이(lift)를
    계산한다. lift가 양수면 그 컴포넌트가 이 클러스터의 선택에 실제로 더 크게 작용했다는
    뜻이라 가중치를 올릴 근거가 된다.

    event 형태: {"chooser_cluster_key": str, "selected_candidate_id": Any,
                 "shown_candidates": [{"candidate_id": Any, "component_scores": {..}}, ...]}

    양의 lift만 반환한다 — 음의 lift로 가중치를 깎는 건 하지 않는다. 이미
    `PENALTY_RULES`(app/scoring/engine.py)가 명시적 배제 신호(예: beginner_fit==0.0)를
    처리하고 있어 역할이 겹치지 않게 하기 위함이다.
    """
    by_cluster: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        by_cluster[event["chooser_cluster_key"]].append(event)

    result: dict[str, dict[str, float]] = {}
    for cluster_key, cluster_events in by_cluster.items():
        if len(cluster_events) < min_events:
            continue

        lifts: dict[str, float] = {}
        for component in components:
            selected_scores = []
            all_shown_scores = []
            for event in cluster_events:
                selected_id = event["selected_candidate_id"]
                for candidate in event["shown_candidates"]:
                    score = candidate["component_scores"].get(component)
                    if score is None:
                        continue
                    all_shown_scores.append(score)
                    if candidate["candidate_id"] == selected_id:
                        selected_scores.append(score)

            if not selected_scores or not all_shown_scores:
                continue

            avg_selected = sum(selected_scores) / len(selected_scores)
            avg_shown = sum(all_shown_scores) / len(all_shown_scores)
            lift = avg_selected - avg_shown
            if lift > 1e-9:
                lifts[component] = lift

        if lifts:
            result[cluster_key] = lifts

    return result


def adjust_weights(
    base_weights: dict[str, float], lifts: dict[str, float], gain: float = 1.0
) -> dict[str, float]:
    """lift가 있는 컴포넌트의 가중치를 lift에 비례해 올리고, 전체 가중치 합은 base_weights와
    동일하게 재정규화한다 — 총점 스케일이 프로덕션과 그대로 비교 가능하다. 컴포넌트 점수 자체는
    건드리지 않으므로 1.0 상한에 의한 변별력 손실이 없다."""
    if not lifts:
        return dict(base_weights)

    raw = {name: weight * (1 + gain * lifts.get(name, 0.0)) for name, weight in base_weights.items()}
    raw_total = sum(raw.values())
    target_total = sum(base_weights.values())
    if raw_total == 0:
        return dict(base_weights)

    scale = target_total / raw_total
    return {name: value * scale for name, value in raw.items()}
