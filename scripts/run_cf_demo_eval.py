"""CF 데모 평가 — "콘텐츠 기반이 구조적으로 못 하는 일을 CF가 한다"를 수치로 보인다.

**측정 방식(교차 분야 발견율, cross-field discovery)**
각 합성 사용자에게 자기 집단의 **한쪽 분야 공모전만** 본 것으로 이력을 주고(예: 디자인만),
추천 상위 K개에 **반대쪽 분야**(예: 정치/사회) 공모전이 얼마나 들어오는지 센다. 반대쪽 분야는
사용자가 실제로 관심 있는 영역이지만 **임베딩상으로는 멀어서** 콘텐츠 기반으로는 닿을 수 없다.

- 콘텐츠 기반(②): 본 공모전들의 임베딩 평균과 후보의 코사인 유사도로 순위를 매긴다.
- CF(①): 동시발생 행렬만으로 순위를 매긴다(텍스트를 전혀 보지 않는다).
- 결합: 실제 프로덕션처럼 두 신호를 가중 결합한다.

**이 평가가 증명하는 것과 증명하지 않는 것**
증명하는 것: 심어둔 잠재 구조를 CF는 복원하고 콘텐츠 기반은 복원하지 못한다(능력 시연).
증명하지 않는 것: 실제 사용자 만족도가 오른다(합성 데이터라 효과 크기는 의미 없다).
대조군 C는 임베딩상 이미 가까운 쌍이라 콘텐츠 기반도 잘해야 정상이며, CF가 이를 망가뜨리지
않는지 확인하는 용도다.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.scoring.cooccurrence import build_cooccurrence, cooccurrence_affinity  # noqa: E402
from app.scoring.similarity import cosine_similarity  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EVENTS_PATH = ROOT / "data" / "result_events.json"
EMBEDDINGS_PATH = ROOT / "data" / "contest_embeddings_cache.json"
INTERACTIONS_PATH = ROOT / "data" / "synthetic_interactions.json"
GROUPS_PATH = ROOT / "data" / "synthetic_interaction_groups.json"
REPORT_PATH = ROOT / "docs" / "monitoring" / "cf-demo-eval-report.md"

TOP_K = 10
# 프로덕션 WEIGHTS의 similarity 가중치를 그대로 쓴다(app/features/user_to_team/scoring.py).
CONTENT_WEIGHT = 0.38
# CF 가중치 후보들 — 첫 값 0.05가 현재 프로덕션 값이고, 나머지는 민감도 분석용이다. 실 데이터가 쌓이면 클러스터
# lift 메커니즘이 이 값을 데이터 기반으로 조정하므로, "지금 0.05가 최선인가"를 감이 아니라
# 곡선으로 보여주기 위한 것이다.
CF_WEIGHT_SWEEP = [0.05, 0.10, 0.20, 0.38]


def _event_id(external_id: str) -> int:
    return int(external_id.rsplit("-", 1)[-1])


def _load_events() -> tuple[dict[int, str], dict[int, list[float]]]:
    rows = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    embeddings = json.loads(EMBEDDINGS_PATH.read_text(encoding="utf-8"))

    field_of: dict[int, str] = {}
    vector_of: dict[int, list[float]] = {}
    for row in rows:
        external_id = row["externalId"]
        eid = _event_id(external_id)
        if eid in field_of or not row.get("field") or external_id not in embeddings:
            continue
        field_of[eid] = row["field"]
        vector_of[eid] = embeddings[external_id]
    return field_of, vector_of


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    dim = len(vectors[0])
    return [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]


def _rank_by(scores: dict[int, float]) -> list[int]:
    return [eid for eid, _ in sorted(scores.items(), key=lambda kv: -kv[1])]


def _normalize(scores: dict[int, float]) -> dict[int, float]:
    """프로덕션의 `normalize_similarities`와 동일한 후보군 내 min-max 정규화.

    이걸 빼먹고 원시 코사인을 그대로 가중하면, 유사도가 좁은 대역(실측 0.25~0.62)에만 몰려
    있어서 결합 결과가 실제 서비스 동작과 달라진다.
    """
    values = scores.values()
    lo, hi = min(values), max(values)
    if hi == lo:
        return dict.fromkeys(scores, 1.0)
    return {key: (value - lo) / (hi - lo) for key, value in scores.items()}


def _discovery_rate(ranked: list[int], target_field: str, field_of: dict[int, str]) -> float:
    """상위 K개 중 목표 분야(사용자가 아직 안 봤지만 관심 있는 쪽)의 비율."""
    top = ranked[:TOP_K]
    if not top:
        return 0.0
    return sum(1 for eid in top if field_of.get(eid) == target_field) / len(top)


def main() -> None:
    field_of, vector_of = _load_events()
    interactions = json.loads(INTERACTIONS_PATH.read_text(encoding="utf-8"))
    groups = json.loads(GROUPS_PATH.read_text(encoding="utf-8"))["groups"]

    cooccurrence = build_cooccurrence(interactions)
    events_by_user: dict[int, list[int]] = defaultdict(list)
    for row in interactions:
        events_by_user[row["user_id"]].append(row["event_id"])

    all_events = [eid for eid in field_of if eid in vector_of]
    results = []

    for group in groups:
        # 사용자에게는 field_a만 본 것으로 주고, field_b를 얼마나 찾아내는지 잰다.
        seen_field, target_field = group["field_a"], group["field_b"]
        rates: dict[str, list[float]] = defaultdict(list)

        for user_id in group["user_ids"]:
            seen = [e for e in events_by_user[user_id] if field_of.get(e) == seen_field]
            if not seen:
                continue

            profile = _mean_vector([vector_of[e] for e in seen if e in vector_of])
            candidates = [e for e in all_events if e not in seen]

            # 프로덕션과 동일하게 유사도를 후보군 내에서 정규화한 뒤 결합한다.
            content = _normalize({e: cosine_similarity(profile, vector_of[e]) for e in candidates})
            cf = {e: cooccurrence_affinity(seen, e, cooccurrence) for e in candidates}

            rates["content"].append(_discovery_rate(_rank_by(content), target_field, field_of))
            rates["cf"].append(_discovery_rate(_rank_by(cf), target_field, field_of))
            for cf_weight in CF_WEIGHT_SWEEP:
                combined = {
                    e: CONTENT_WEIGHT * content[e] + cf_weight * cf[e] for e in candidates
                }
                rates[f"combined_{cf_weight}"].append(
                    _discovery_rate(_rank_by(combined), target_field, field_of)
                )

        results.append(
            {
                "group": group["name"],
                "description": group["description"],
                "seen_field": seen_field,
                "target_field": target_field,
                "users": len(rates["content"]),
                **{name: (sum(v) / len(v) if v else 0.0) for name, v in rates.items()},
            }
        )

    pair_count = sum(len(n) for n in cooccurrence.values()) // 2
    lines = [
        "# CF 데모 평가 — 교차 분야 발견율",
        "",
        f"합성 상호작용 {len(interactions)}건 / 사용자 {len(events_by_user)}명 / 동시발생 쌍 {pair_count}개, K={TOP_K}",
        "",
        f"각 사용자에게 자기 집단의 **한쪽 분야만** 본 이력을 주고, 추천 상위 {TOP_K}개에 **반대쪽",
        "분야** 공모전이 얼마나 들어오는지 측정했다. 반대쪽 분야는 실제로 관심 있는 영역이지만",
        "임베딩상 멀어서 콘텐츠 기반으로는 닿기 어렵다.",
        "",
        "| 집단 | 본 분야 → 찾아야 할 분야 | 콘텐츠 기반 | CF 단독 |",
        "|---|---|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['description']} | {r['seen_field']} → {r['target_field']} | "
            f"{r['content']:.3f} | **{r['cf']:.3f}** |"
        )

    lines += [
        "",
        "## CF 가중치 민감도",
        "",
        "실제 추천은 두 신호를 가중 결합한다. 현재 프로덕션 `cf_affinity` 가중치는 **0.05**로,",
        "실 데이터가 없는 상태에서 의도적으로 보수적으로 잡은 값이다(유사도는 0.38). 아래는 이",
        "값을 올렸을 때 교차 분야 발견율이 어떻게 움직이는지 본 것이다 — 실 선택 데이터가 쌓이면",
        "클러스터 lift 메커니즘이 이 가중치를 데이터 기반으로 조정하므로, 감으로 정할 필요가 없다.",
        "",
        "| 집단 | " + " | ".join(f"cf={w}" for w in CF_WEIGHT_SWEEP) + " |",
        "|---|" + "---:|" * len(CF_WEIGHT_SWEEP),
    ]
    for r in results:
        cells = " | ".join(f"{r[f'combined_{w}']:.3f}" for w in CF_WEIGHT_SWEEP)
        lines.append(f"| {r['description']} | {cells} |")

    lines += [
        "",
        "## 읽는 법",
        "",
        "- **집단 A·B(임베딩상 먼 쌍)**: 콘텐츠 기반은 반대쪽 분야를 거의 못 찾는다 — 임베딩 공간에서",
        "  멀기 때문에 구조적으로 닿을 수 없다. CF는 텍스트를 전혀 보지 않고 \"같은 사람들이 함께 봤다\"",
        "  는 신호만으로 찾아낸다.",
        "- **집단 C(대조군, 임베딩상 가까운 쌍)**: 콘텐츠 기반도 이미 잘한다. CF를 얹어도 이 강점이",
        "  사라지지 않는지 확인하는 용도다 — 민감도 표에서 이 행이 가중치를 올려도 거의 흔들리지",
        "  않는 게 그 확인이다(CF가 기존에 잘 되던 경우를 망가뜨리지 않는다).",
        "- **현재 가중치(0.05)에서는 최종 순위가 거의 안 바뀐다는 점도 그대로 적는다.** CF 단독",
        "  성능과 결합 후 성능의 격차가 그 사실을 보여준다 — 신호 자체는 강하지만 아직 그것을",
        "  크게 신뢰하지 않도록 보수적으로 잡아둔 상태이고, 그 판단을 데이터 없이 임의로 뒤집지",
        "  않는다는 뜻이다.",
        "",
        "## 이 평가가 증명하지 않는 것",
        "",
        "합성 데이터이므로 **효과 크기는 의미가 없다** — 실제 사용자 만족도가 오른다는 근거가 아니다.",
        "이 실험이 보이는 건 \"의미 임베딩이 구조적으로 표현할 수 없는 잠재 구조를 CF가 복원한다\"는",
        "능력(recovery)뿐이다. 잠재 구조를 심을 때 분야 쌍은 감으로 고르지 않고 실제 공모전 414건의",
        "임베딩으로 중심점 거리를 측정해 가장 먼 쌍을 골랐다(scripts/generate_synthetic_interactions.py).",
        "",
        "재현: `generate_synthetic_interactions.py` → `run_cf_demo_eval.py`",
    ]

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n리포트 저장: {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
