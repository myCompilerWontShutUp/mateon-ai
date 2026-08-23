"""공모전 지형도 — 네 번째 방식(2026-08-23, 사용자 요청). 장르 기반 배치(버블/앵커)를 전부
버리고 **쿼리 공모전 1건 중심의 유사도 방사형 배치**로 바꾼다.

- BE가 특정 공모전(쿼리) ID를 보내면, AI 서버는 그 공모전을 원점(0,0)에 고정하고 나머지
  후보들과의 임베딩 코사인 유사도를 계산한다. 이번엔 진짜 임베딩이 다시 필요하다 — 다행히
  `data/contest_embeddings_cache.json`에 414건 전부의 실제 `text-embedding-3-small` 벡터가
  이미 캐싱돼 있어(이전 장르 기반 방식이 안 쓰게 된 뒤에도 삭제하지 않고 남겨뒀다) **새 API
  호출이 전혀 필요 없다.**
- **후보 집합**: 쿼리를 제외한 나머지 중 유사도 상위 `top_n`건(기본 500 — 지금 데이터가
  413건뿐이라 사실상 전부 포함된다. 나중에 후보 풀이 500건을 넘으면 그때부터 실제로 컷이
  걸린다). **`query_contest_id`/`top_n` 둘 다 함수 파라미터로 뺐다**(2026-08-23, 사용자 요청 —
  "top 500으로 설정한 구간을 BE에서 파라미터로 전송할 수 있게") — `build_visualization()`을
  직접 호출하거나 `--query-contest-id`/`--top-n` CLI 인자로 넘길 수 있다. 지금은 여전히 스크립트
  호출 파라미터일 뿐 실제 HTTP 요청 파라미터는 아니다 — 나중에 진짜 엔드포인트로 옮길 때
  그대로 요청 스키마 필드가 될 자리를 미리 만들어둔 것.
- **반지름 매핑 — 세 번 고쳤다(전부 2026-08-23, 실측 피드백으로 발견).**
  1. 처음엔 `radius = MAX_RADIUS * (1 - similarity)`뿐이었다 — 유사도가 가장 높은(=가장
     중요한) 공모전이 반지름 0에 가까워져 **중앙 쿼리 점과 겹쳐버렸다.**
  2. `MIN_RADIUS`를 더해(`radius = MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * (1 - similarity)`)
     유사도 1이어도 반지름의 바깥 경계는 0이 안 되게 했지만, **실제 난수는 여전히 `[0, radius]`
     전체에서 뽑혀서** 유사도 1이어도 우연히 중심 근처(r≈0)가 나올 수 있었다 — 겹침이 그대로
     재현됨.
  3. 안쪽 경계 `INNER_FLOOR`를 추가해 `[INNER_FLOOR, radius]` 고리(annulus) 안에서만 뽑도록
     고쳤는데, **이 안쪽 경계가 모든 점에 공통이라는 게 새 문제였다** — 유사도가 낮아
     반지름(바깥 경계)이 큰 점도, 난수가 우연히 그 공통 안쪽 경계 근처로 뽑히면 **유사도 낮은
     회색 점이 중앙 바로 옆에 찍히는 문제**가 실측으로 나왔다(사용자가 스크린샷으로 지적).
  4. `ideal_radius = MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * (1 - similarity)`를 중심으로
     **아주 좁은 폭(`RADIAL_JITTER`, ±0.5)만** 무작위로 흔들어 "반지름 범위 공유"라는 근본
     원인을 없앴다 — 서로 다른 유사도대끼리는 반지름 범위가 겹칠 수 없고, 비슷한 유사도끼리만
     자연스럽게 흩어져 보인다.
  5. **그래도 부족했다** — 절대 유사도를 그대로 반지름에 매핑하니, 실제 데이터가 0.25~0.62
     라는 좁은 대역에만 있어서 유사도 0.7/0.9 근처엔 점이 하나도 안 찍히고 전부 바깥쪽 절반에만
     몰려 "다 멀어 보인다"는 문제가 실측으로 나왔다(2026-08-23, 사용자 피드백) — 색상이 이미
     겪었던 것과 정확히 같은 원인이다. 그래서 **반지름도 색과 똑같이 순위(rank) 기반**으로
     바꿨다: `t = rank / (n-1)`(0=1등=가장 유사, 1=꼴찌), `radius = MIN_RADIUS + (MAX_RADIUS -
     MIN_RADIUS) * t`. 1등은 항상 MIN_RADIUS, 꼴찌는 항상 MAX_RADIUS, 나머지는 순위 순서대로
     고르게 퍼진다 — **절대 유사도 숫자와 반지름의 직접 대응은 이제 없다**("유사도 0.9면 이
     정도 거리"라는 해석은 더 이상 성립하지 않는다). 대신 참고선(reference ring)을 절대값이
     아니라 **백분위**로 다시 그리고, 그 백분위 경계에 실제 어떤 유사도 값이 대응하는지도 같이
     보여준다(`reference_rings`, 각도(theta)는 여전히 0~2π 균등 난수 — 방향 자체엔 의미가
     없어서 그대로 둔다).
- **색상**: 카테고리가 아니라 **거리(=유사도)의 연속값**을 표현한다 — 멀수록(비유사) 회색,
  가까울수록(유사) 파란색. 실제 색 계산은 이 스크립트가 아니라 프론트(JS, 아티팩트 템플릿)에서
  하는데, 이것도 두 번 고쳤다: (1) 절대 척도(0~1) 그대로 매겼더니 실제 후보들이 좁은 대역
  (0.25~0.62)에 몰려 있어 색이 전부 비슷해 보였고, (2) 후보군 안에서 min-max 정규화해도
  유사도 분포가 종모양(정규분포에 가까움)이라 대다수 점이 회색·파랑 절반씩 섞인 색에 몰렸다
  (RGB 선형보간은 무채색·유채색을 50:50 섞어도 사람 눈엔 유채색 쪽으로 치우쳐 보임). 최종적으로
  **순위(rank) 기반**으로 바꿔 분포 모양과 무관하게 회색↔파랑 전체 구간이 고르게 쓰이게 했다.
- **점↔중앙점 연결선**: 모든 점을 쿼리(중앙) 점과 선으로 잇는다(2026-08-23 추가 요청) —
  점끼리는 연결하지 않는다. 선 자체는 시각화 레이어(프론트 JS)에서 그린다 — 좌표만 있으면
  선분은 항상 (0,0)에서 각 점까지이므로 데이터로 따로 들고 있을 이유가 없다.

**출력은 여전히 시각화 검증용 JSON일 뿐이다** — 이 데이터를 실제 BE 응답 계약으로 다듬는 건
다음 단계(사용자가 이번엔 "우선 테스트를 위해 시각화"라고 명시).
"""

import argparse
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from app.schemas.contest import CONTEST_FIELD_LABELS, ContestField  # noqa: E402
from app.scoring.similarity import cosine_similarity  # noqa: E402

INPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "result_events.json"
EMBEDDING_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "contest_embeddings_cache.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "contest_similarity_visualization.json"

LAYOUT_RANDOM_SEED = 20260823
MAX_RADIUS = 12.0
MIN_RADIUS = 2.6  # 유사도 1.0일 때의 반지름(중앙에서 이만큼은 항상 떨어짐)
RADIAL_JITTER = 0.5  # 각 점의 반지름을 자기 유사도가 정한 값 근처에서만 살짝 흩는 폭
DEFAULT_TOP_N = 500  # BE가 안 보내면 쓰는 기본값 — 2026-08-23부터 top_n을 파라미터로 뺐다


def _load_unique_contests() -> dict[str, dict]:
    raw = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    contests: dict[str, dict] = {}
    for row in raw:
        eid = row["externalId"]
        if eid not in contests:
            contests[eid] = {**row, "fields": [], "primary_field": row["field"]}
        contests[eid]["fields"].append(row["field"])
    return contests


def _field_label(field_code: str) -> str:
    try:
        return CONTEST_FIELD_LABELS[ContestField(field_code)]
    except ValueError:
        return field_code


def build_visualization(query_contest_id: str | None = None, top_n: int = DEFAULT_TOP_N) -> dict:
    """`query_contest_id`와 `top_n` 둘 다 BE가 실제로 보낼 값이라고 가정하고 파라미터로
    뺐다(2026-08-23, 사용자 요청 — "top 500으로 설정한 구간을 BE에서 파라미터로 전송할 수
    있게"). `query_contest_id`가 없으면 정렬된 ID 중 첫 번째를 테스트용으로 쓴다(임의로
    "그럴듯해 보이는" 걸 고르지 않기 위해 결정론적으로)."""
    contests = _load_unique_contests()
    ids = sorted(contests)

    cache = json.loads(EMBEDDING_CACHE_PATH.read_text(encoding="utf-8"))
    missing = [eid for eid in ids if eid not in cache]
    if missing:
        raise SystemExit(f"임베딩 캐시에 없는 공모전 {len(missing)}건 발견 — 캐시가 최신 데이터와 안 맞음: {missing[:5]}")

    query_id = query_contest_id or ids[0]
    if query_id not in contests:
        raise SystemExit(f"쿼리 공모전 ID를 찾을 수 없음: {query_id}")
    query = contests[query_id]
    query_vec = cache[query_id]
    print(f"쿼리 공모전: {query_id} — {query['title']} ({query['primary_field']})")

    scored = []
    for eid in ids:
        if eid == query_id:
            continue
        sim = cosine_similarity(query_vec, cache[eid])
        scored.append((eid, sim))
    scored.sort(key=lambda pair: -pair[1])
    top = scored[:top_n]
    print(f"후보 {len(ids) - 1}건 중 유사도 상위 {len(top)}건 선정(top_n={top_n}) "
          f"(최고 {top[0][1]:.3f}, 최저 {top[-1][1]:.3f})")

    # **반지름도 결국 순위(rank) 기반으로 바꿨다** — 절대 유사도(0~1) 그대로 반지름에 매핑하면
    # 실제 데이터가 0.25~0.62라는 좁은 대역에만 있어서, 유사도 0.7/0.9 근처엔 점이 하나도 안
    # 찍히고 전부 바깥쪽 절반에만 몰려 "다 멀어 보인다"는 문제가 실측으로 나왔다(2026-08-23,
    # 사용자 피드백) — 색상이 겪었던 것과 똑같은 원인이다. 그래서 색과 완전히 같은 원리로,
    # "지금 보여주는 후보군 안에서" 상위 몇 %인지로 반지름을 정한다 — 1등(가장 유사)은 항상
    # MIN_RADIUS, 꼴찌는 항상 MAX_RADIUS, 나머지는 그 사이에 순위 순서대로 고르게 퍼진다.
    # **이러면 절대 유사도 숫자와 반지름의 직접적 대응은 사라진다** — "유사도 0.9면 이 정도
    # 거리"라는 해석은 더 이상 성립하지 않고, 오직 "지금 보여주는 후보들 중 상대적으로 몇 번째로
    # 유사한가"만 거리로 표현된다. 이 트레이드오프를 감수하는 대신, 대신 아래 참고선을 절대값이
    # 아니라 백분위(상위 n%)로 다시 그려서 — 그 백분위 경계에 실제 어떤 유사도 값이 대응하는지도
    # 라벨로 같이 보여준다.
    n = len(top)
    rng = random.Random(LAYOUT_RANDOM_SEED)
    points = []
    for rank, (eid, sim) in enumerate(top):
        c = contests[eid]
        t = rank / (n - 1) if n > 1 else 0.0
        ideal_radius = MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * t
        # 반지름을 자기 순위가 정한 값(ideal_radius) 근처에서만 아주 좁게 흔든다 — 서로 다른
        # 순위대끼리는 반지름 범위가 절대 안 겹치고, 비슷한 순위끼리만 자연스럽게 흩어져 보인다
        # (이전엔 모든 점이 공통 안쪽 경계를 공유하는 고리에서 뽑아서, 유사도 낮은 점도 우연히
        # 중앙 근처로 뽑히는 문제가 있었다 — 2026-08-23 실측으로 발견·수정).
        r = max(0.3, ideal_radius + rng.uniform(-RADIAL_JITTER, RADIAL_JITTER))
        theta = rng.uniform(0, 2 * math.pi)
        points.append(
            {
                "id": eid,
                "title": c["title"],
                "organizer": c.get("organizer"),
                "category": c.get("category"),
                "field": c["primary_field"],
                "field_label": _field_label(c["primary_field"]),
                "detail_url": c.get("detailUrl"),
                "similarity": sim,
                "rank_percentile": t,
                "radius": ideal_radius,
                "x": r * math.cos(theta),
                "y": r * math.sin(theta),
            }
        )

    # 참고선(reference ring)도 절대 유사도(0.9/0.7/0.5/0.3)가 아니라 **백분위**로 다시 그린다 —
    # 반지름이 이제 순위 기반이라, 절대값 기준 링은 실제 데이터가 하나도 안 닿는 빈 원이 되기
    # 때문이다(2026-08-23). 각 백분위 경계에 실제로 어떤 유사도 값이 대응하는지도 같이 담아서,
    # "상위 10%"가 숫자로는 어느 정도인지 화면에서 확인할 수 있게 한다.
    reference_percentiles = [0.1, 0.3, 0.6, 0.9]
    reference_rings = []
    for p in reference_percentiles:
        idx = min(n - 1, int(round(p * (n - 1))))
        reference_rings.append(
            {
                "percentile": p,
                "similarity_at_percentile": top[idx][1],
                "radius": MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * p,
            }
        )

    output = {
        "query": {
            "id": query_id,
            "title": query["title"],
            "organizer": query.get("organizer"),
            "category": query.get("category"),
            "field": query["primary_field"],
            "field_label": _field_label(query["primary_field"]),
            "detail_url": query.get("detailUrl"),
        },
        "points": points,
        "max_radius": MAX_RADIUS,
        "min_radius": MIN_RADIUS,
        "radial_jitter": RADIAL_JITTER,
        "reference_rings": reference_rings,
        "candidate_pool_total": len(ids) - 1,
        "layout_method": "query-centered similarity RANK-based radial layout — points are sorted "
        "by cosine_similarity and placed by rank percentile (radius = MIN_RADIUS + (MAX_RADIUS - "
        "MIN_RADIUS) * rank_percentile), NOT by the raw absolute similarity value, because the real "
        "similarity distribution is narrow (~0.25-0.62) and an absolute mapping left everything "
        "crowded in the outer half with the 0.7/0.9 reference rings empty; each point's radius is "
        "jittered by a small fixed amount around its own rank-derived radius so different rank bands "
        "never overlap; color encodes the same rank percentile as a continuous gray(far)->blue(near) "
        "ramp, computed client-side; every point is also line-connected to the query marker",
    }
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query-contest-id",
        default=None,
        help="쿼리로 쓸 공모전 externalId. 안 주면 정렬된 ID 중 첫 번째를 테스트용으로 쓴다.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"유사도 상위 몇 건까지 표시할지(BE가 보낼 파라미터, 기본값 {DEFAULT_TOP_N}).",
    )
    args = parser.parse_args()

    output = build_visualization(query_contest_id=args.query_contest_id, top_n=args.top_n)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(output['points'])} points to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
