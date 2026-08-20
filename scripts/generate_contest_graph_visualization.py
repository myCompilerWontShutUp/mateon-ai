"""그래프형 시각화(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 7번) 대상 정정 — 애초 팀/유저
제안·역제안 관계로 잘못 잡았으나, 실제 요구사항은 제안 관계와 무관하게 **공모전/대외활동 공고를
서로 얼마나 비슷한지 2차원에 배치하고 분야(ContestField)별로 색칠**하는 것이었다
(2026-08-20 정정). BE가 실제로 수집한 공모전 데이터(`data/result_events.json`, Linkareer
스크래핑 결과로 보이는 실 데이터)를 그대로 쓴다 — 이전 팀/유저 fixture와 달리 합성이 아니다.
pytest가 쓰는 값이 아니라 이 스크립트 전용 입출력이라 `tests/fixtures/`가 아니라 `data/`에
둔다(2026-08-20, 사용자 피드백으로 위치 정정 — `tests/fixtures/teams.json`처럼 실제
`test_*.py`가 로드하는 파일과 섞이면 혼동됨).

**2차원 축소 방식(2026-08-20 재정정)**: 처음엔 순수 PCA로 2차원까지 바로 줄였는데, 실측 결과
"같은 장르끼리 가까이"가 전혀 안 보였다(PC1+PC2 설명 분산 11.9%뿐 — PCA는 전역 분산이 가장 큰
방향을 찾을 뿐 지역적 이웃 관계를 보존하지 않아서, 애초에 이 목적에 안 맞는 도구였다).
**PCA로 1536→100차원까지 노이즈를 걷어낸 뒤 UMAP으로 100→2차원 축소**(이웃 관계 보존이 목적함수)
로 바꿨다 — UMAP 자체 문서가 권장하는 표준 전처리 순서이기도 하다. 원본 1536차원 벡터는
`data/contest_embeddings_cache.json`에 캐싱해서, 축소 기법을 다시 바꾸더라도 API를 재호출하지
않아도 되게 했다.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import umap

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.openai_client.embedding import embed_text  # noqa: E402
from app.schemas.contest import CONTEST_FIELD_LABELS, ContestField  # noqa: E402

INPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "result_events.json"
EMBEDDING_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "contest_embeddings_cache.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "contest_graph_visualization.json"

PCA_COMPONENTS = 100  # UMAP 전처리 — 1536차원 노이즈를 걷어내고 의미 있는 축만 남긴다.
UMAP_RANDOM_STATE = 20260820  # 재현 가능한 레이아웃(같은 입력이면 항상 같은 좌표가 나오게)

# dataviz 스킬 palette.md 실측: 이 8색 순서는 "인접 쌍"(막대/선 등) 기준으로 검증된 것이고,
# 산점도처럼 모든 점이 동시에 보이는 "전 쌍"(all-pairs) 형태에서는 처음 3개(파랑/주황/아쿠아)만
# 전 쌍 검증을 통과한다(문서: "the first three slots validate all-pairs ... Past three, fold to
# Other or facet"). 여기는 분야가 20개라 원칙대로면 3개 넘는 순간 전부 "기타"로 묶어야 하지만,
# 그러면 장르 구분이라는 요청 목적 자체가 무의미해진다 — 상위 8개 분야까지는 절충으로 8슬롯을
# 다 쓰되(4번째부터는 전 쌍 검증 미통과 상태임을 알고 쓰는 것), 그 밖의 장기 꼬리 분야는 전부
# 뉴트럴 회색(표의 "Muted" 잉크, 라이트/다크 공통값)으로 묶는다. 색상만으로 구분하지 않도록
# 모든 노드에 실제 분야명을 항상 같이 담는다(text_는 색과 무관하게 항상 정확한 값).
_VALIDATED_8_SLOTS = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]
_OTHER_COLOR = "#898781"
_OTHER_BUCKET_LABEL = "기타(장기 꼬리 분야 묶음)"


def _load_unique_contests() -> dict[str, dict]:
    """externalId 기준으로 중복 제거하고, 그 공모전에 처음 등장한 field를 '대표 분야'로 쓴다
    (한 공모전이 여러 분야에 걸쳐 있을 수 있어 다중 태그 배열 대신 행이 여러 개로 온다 — 팀의
    다중 recruiting_roles에서 roles[0]을 대표값으로 쓰던 것과 같은 패턴). 어떤 태그가 먼저
    오는지는 BE 파이프라인이 정한 순서를 그대로 신뢰한다 — AI 서버가 "무엇이 더 중요한 분야인지"
    재판단할 근거가 없다.
    """
    raw = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    contests: dict[str, dict] = {}
    for row in raw:
        eid = row["externalId"]
        if eid not in contests:
            contests[eid] = {**row, "primary_field": row["field"]}
    return contests


def _embedding_text(contest: dict) -> str:
    parts = [
        f"제목: {contest['title']}",
        f"주최: {contest.get('organizer') or '미상'}",
        f"요약: {contest.get('summarizedDescription') or (contest.get('description') or '')[:500]}",
    ]
    if contest.get("recommendedTargets"):
        parts.append(f"추천 대상: {contest['recommendedTargets']}")
    return "\n".join(parts)


async def _get_vectors(ids: list[str], contests: dict[str, dict]) -> np.ndarray:
    """캐시가 전체 id를 커버하면 재사용하고, 아니면 전부 다시 embed해서 캐시를 새로 쓴다 —
    부분 무효화는 안 하는 단순한 방식(이 스크립트 규모에서 그 이상은 과설계)."""
    if EMBEDDING_CACHE_PATH.exists():
        cache = json.loads(EMBEDDING_CACHE_PATH.read_text(encoding="utf-8"))
        if set(ids) <= set(cache):
            print(f"embedding cache hit — reusing {len(ids)}건 (API 재호출 없음)")
            return np.array([cache[eid] for eid in ids])

    cache = {}
    for i, eid in enumerate(ids, start=1):
        text = _embedding_text(contests[eid])
        cache[eid] = await embed_text(text)
        print(f"[{i}/{len(ids)}] embedded {eid} ({contests[eid]['title'][:30]}...)")
    EMBEDDING_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return np.array([cache[eid] for eid in ids])


def _pca_reduce(vectors: np.ndarray, n_components: int) -> np.ndarray:
    centered = vectors - vectors.mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    return centered @ vt[:n_components].T


def _genre_separation_ratio(vectors: np.ndarray, labels: list[str]) -> float:
    """between-group / within-group 분산비 — 장르가 원본 임베딩 공간에 실제로 신호로 존재하는지
    최종 2D 투영과 무관하게 확인하는 진단(1536차원 원본 벡터 기준). 1보다 크면 "장르가 무작위
    배치보다는 어느 정도 갈린다"는 뜻, 1 미만이면 이 축소 기법을 뭘 써도 장르별로 안 갈린다는
    뜻이라 투영 기법을 바꿔봐야 소용없다는 신호다."""
    labels_arr = np.array(labels)
    overall_mean = vectors.mean(axis=0)
    between = 0.0
    within = 0.0
    for label in set(labels_arr):
        mask = labels_arr == label
        group = vectors[mask]
        group_mean = group.mean(axis=0)
        between += mask.sum() * np.sum((group_mean - overall_mean) ** 2)
        within += np.sum((group - group_mean) ** 2)
    return float(between / within) if within else 0.0


def _field_color_map(primary_fields: list[str]) -> dict[str, str]:
    freq = Counter(primary_fields).most_common()
    return {field: (_VALIDATED_8_SLOTS[i] if i < len(_VALIDATED_8_SLOTS) else _OTHER_COLOR) for i, (field, _) in enumerate(freq)}


def _field_label(field_code: str) -> str:
    try:
        return CONTEST_FIELD_LABELS[ContestField(field_code)]
    except ValueError:
        return field_code


async def main() -> None:
    contests = _load_unique_contests()
    ids = sorted(contests)
    primary_fields = [contests[eid]["primary_field"] for eid in ids]

    vectors = await _get_vectors(ids, contests)

    separation_ratio = _genre_separation_ratio(vectors, primary_fields)
    print(f"장르 분리 진단(원본 1536차원 기준 between/within 분산비): {separation_ratio:.3f}")

    reduced = _pca_reduce(vectors, PCA_COMPONENTS)
    reducer = umap.UMAP(n_components=2, metric="cosine", random_state=UMAP_RANDOM_STATE)
    coords = reducer.fit_transform(reduced)

    color_map = _field_color_map(primary_fields)

    nodes = []
    for i, eid in enumerate(ids):
        c = contests[eid]
        field_code = c["primary_field"]
        x, y = coords[i]
        nodes.append(
            {
                "id": eid,
                "title": c["title"],
                "organizer": c.get("organizer"),
                "category": c.get("category"),
                "field": field_code,
                "field_label": _field_label(field_code),
                "detail_url": c.get("detailUrl"),
                "x": float(x),
                "y": float(y),
                "color": color_map[field_code],
            }
        )

    legend = [
        {"field": field, "field_label": _field_label(field), "color": color}
        for field, color in color_map.items()
        if color != _OTHER_COLOR
    ]
    other_fields = [f for f, c in color_map.items() if c == _OTHER_COLOR]
    if other_fields:
        legend.append({"field": None, "field_label": _OTHER_BUCKET_LABEL, "color": _OTHER_COLOR})

    output = {
        "nodes": nodes,
        "legend": legend,
        "dimensionality_reduction": f"PCA(1536->{PCA_COMPONENTS}) + UMAP({PCA_COMPONENTS}->2, cosine)",
        "genre_separation_ratio": separation_ratio,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(nodes)} nodes to {OUTPUT_PATH}")
    print(f"color_map: {color_map}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
