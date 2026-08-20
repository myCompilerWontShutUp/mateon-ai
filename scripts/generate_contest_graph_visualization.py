"""그래프형 시각화(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 7번) 대상 정정 — 애초 팀/유저
제안·역제안 관계로 잘못 잡았으나, 실제 요구사항은 제안 관계와 무관하게 **공모전/대외활동 공고를
서로 얼마나 비슷한지 2차원에 배치하고 분야(ContestField)별로 색칠**하는 것이었다
(2026-08-20 정정). BE가 실제로 수집한 공모전 데이터(`data/result_events.json`, Linkareer
스크래핑 결과로 보이는 실 데이터)를 그대로 쓴다 — 이전 팀/유저 fixture와 달리 합성이 아니다.
pytest가 쓰는 값이 아니라 이 스크립트 전용 입출력이라 `tests/fixtures/`가 아니라 `data/`에
둔다(2026-08-20, 사용자 피드백으로 위치 정정 — `tests/fixtures/teams.json`처럼 실제
`test_*.py`가 로드하는 파일과 섞이면 혼동됨).

기존 `generate_graph_visualization.py`(팀/유저·제안 관계 기반)는 삭제했다 — 대상 자체가 틀렸던
설계라 재사용할 게 좌표 축소(PCA) 로직 정도뿐이었다.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.openai_client.embedding import embed_text  # noqa: E402
from app.schemas.contest import CONTEST_FIELD_LABELS, ContestField  # noqa: E402

INPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "result_events.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "contest_graph_visualization.json"

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


def _pca_2d(vectors: np.ndarray) -> np.ndarray:
    centered = vectors - vectors.mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    return centered @ vt[:2].T


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

    vectors = []
    for i, eid in enumerate(ids, start=1):
        text = _embedding_text(contests[eid])
        vector = await embed_text(text)
        vectors.append(vector)
        print(f"[{i}/{len(ids)}] embedded {eid} ({contests[eid]['title'][:30]}...)")

    coords = _pca_2d(np.array(vectors))
    explained = None
    if len(vectors) > 1:
        centered = np.array(vectors) - np.array(vectors).mean(axis=0)
        s = np.linalg.svd(centered, full_matrices=False, compute_uv=False)
        var = s**2
        explained = (var[:2] / var.sum()).tolist()

    primary_fields = [contests[eid]["primary_field"] for eid in ids]
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
        "pca_explained_variance_ratio": explained,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(nodes)} nodes to {OUTPUT_PATH}")
    print(f"PC1+PC2 explained variance: {explained}")
    print(f"color_map: {color_map}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
