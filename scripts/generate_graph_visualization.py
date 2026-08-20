"""4번 항목(그래프형 시각화) — CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 7번.

"Graph RAG"가 아니라 순수 시각화다: 기능 없이 임베딩을 2차원으로 축소한 좌표 + 고정 ENUM
기반 색상 + 관계(제안/역제안) 엣지만 만든다. AI 서버가 프론트엔드에 직접 주지 않고 반드시
AI → BE → FE로 전달돼야 하므로, 이 스크립트는 **데이터(JSON)만** 만든다 — 그 데이터를 실제로
어떻게 BE가 중계할지(신규 엔드포인트 vs 1회성 전달)는 아직 미정이라 여기서 결정하지 않는다.

2번 항목(Hit@10 평가)에서 만든 50 팀·50 유저 fixture를 그대로 재사용한다. 관계(엣지)는 실제
제안/역제안 데이터가 없으므로, 실제 프로덕션 스코어링(app/evaluation/scoring_arms.py, 2번
항목과 동일 코드)으로 유저별 상위 3개 팀 매칭을 계산해 "제안 후보" 관계로 표현한다 — 이건
가짜 데이터가 아니라 실제 임베딩 + 실제 스코어링 로직에서 나온 결과다.

색상 관련 한계(정직하게 명시): dataviz 스킬의 검증된 카테고리 팔레트는 산점도처럼 모든 쌍이
동시에 보이는 차트 형태에서 3개 슬롯까지만 색맹 안전성이 전부 검증돼 있고, 8개까지는 인접
쌍만 검증돼 있다. 여기는 역할 코드가 10개라 그 범위를 넘는다 — 데이터에 `role` 텍스트 필드를
항상 같이 넣어서 "색상만으로 구분"하지 않게 했지만(범례/라벨로 보완 가능하다는 전제), 최종
FE 화면에서 10개 전부를 색으로만 구분하려면 이 팔레트를 그대로 쓰지 말고 재검증하거나 모양
등 2차 인코딩을 추가하는 걸 권장한다.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation.scoring_arms import production_ranking  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
OUTPUT_PATH = FIXTURES_DIR / "graph_visualization.json"

TOP_K_EDGES = 3

# dataviz 스킬 palette.md의 8슬롯 카테고리 팔레트(라이트 모드) — 빈도 상위 8개 역할에 순서대로
# 배정한다. 9~10번째 역할은 검증되지 않은 보조 색상을 쓴다(위 모듈 docstring 한계 참고).
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
_UNVALIDATED_EXTRA = ["#7a5230", "#5a5a5a"]  # brown, gray — 9/10번째용, CVD 미검증


def _primary_role(roles: list[str]) -> str:
    return roles[0] if roles else "ETC"


def _role_color_map(all_roles: list[str]) -> dict[str, str]:
    from collections import Counter

    freq = Counter(all_roles).most_common()
    palette = _VALIDATED_8_SLOTS + _UNVALIDATED_EXTRA
    return {role: palette[i] if i < len(palette) else "#999999" for i, (role, _) in enumerate(freq)}


def _pca_2d_group_demeaned(team_vectors: np.ndarray, user_vectors: np.ndarray) -> np.ndarray:
    """팀/유저를 한 PCA 공간에 같이 투영하되, 그룹별 평균을 먼저 빼고 합친다.

    처음엔 그냥 100개를 합쳐서 전체 평균만 빼고 PCA를 돌렸는데, 실제로 찍어보니 1주성분이
    거의 전부(설명 분산 22%, 팀 평균 -0.305 vs 유저 평균 +0.305, 그룹 내 표준편차는 0.04
    수준) "팀이냐 유저냐"만 가르고 있었다 — `render_team_embedding_text`/
    `render_intent_embedding_text` 템플릿의 문장 구조 차이("팀 소개: " vs "자기소개: ")가
    임베딩 공간에서 내용보다 더 큰 신호였던 것. 이러면 좌표가 항상 팀/유저 두 덩어리로만
    갈리고 "누가 누구와 가까운가"(밀집도)는 안 보인다. 그룹별로 평균을 먼저 빼서 이 신호를
    제거하니(팀/유저 평균이 두 축 모두에서 0으로 정확히 맞춰짐, 1주성분 설명 분산도 8.9%로
    낮아짐) 내용 기반 유사도가 드러난다.
    """
    team_centered = team_vectors - team_vectors.mean(axis=0)
    user_centered = user_vectors - user_vectors.mean(axis=0)
    combined = np.vstack([team_centered, user_centered])
    _, _, vt = np.linalg.svd(combined, full_matrices=False)
    return combined @ vt[:2].T


def main() -> None:
    teams = json.loads((FIXTURES_DIR / "eval_teams.json").read_text(encoding="utf-8"))
    users = json.loads((FIXTURES_DIR / "eval_users.json").read_text(encoding="utf-8"))

    team_ids = sorted(teams, key=int)
    user_ids = sorted(users, key=int)
    team_vectors = np.array([teams[tid]["embedding_vector"] for tid in team_ids])
    user_vectors = np.array([users[uid]["embedding_vector"] for uid in user_ids])
    coords_2d = _pca_2d_group_demeaned(team_vectors, user_vectors)
    team_coords = {tid: coords_2d[i] for i, tid in enumerate(team_ids)}
    user_coords = {uid: coords_2d[len(team_ids) + i] for i, uid in enumerate(user_ids)}

    team_roles = {tid: _primary_role(teams[tid]["metadata"]["recruiting_roles"]) for tid in team_ids}
    user_roles = {uid: _primary_role(users[uid]["metadata"]["desired_roles"]) for uid in user_ids}
    color_map = _role_color_map(list(team_roles.values()) + list(user_roles.values()))

    # 색상이 역할별로 잘 안 갈리는 것에 대한 참고: 실측 결과 팀 쪽은 recruiting_roles로 칠하든
    # contest_field로 칠하든 2D 투영에서 분리가 거의 안 된다(그룹간/그룹내 분산비 각각
    # 0.86/0.84 — 1 미만이면 사실상 무작위 배치와 다르지 않음). 팀 임베딩 텍스트가 모집
    # 역할·공모전 분야·활동 방식·현재 구성을 동시에 담고 있어 단일 필드로는 안 갈리는 구조적
    # 한계이지, 팔레트나 코드 버그가 아니다. 반대로 유저 쪽은 desired_roles 기준 분리비가 3.2로
    # 실제로 어느 정도 갈린다(PCA/color 자체는 그대로 두고 코드 주석으로만 남김 — 사용자 요청에
    # 따라 화면에 캡션은 추가하지 않는다, 2026-08-20).

    edges = []
    for uid in user_ids:
        ranked = production_ranking(users[uid]["embedding_vector"], users[uid]["metadata"], teams)
        for rank, candidate in enumerate(ranked[:TOP_K_EDGES], start=1):
            edges.append(
                {
                    "source": f"user:{uid}",
                    "target": f"team:{candidate.candidate_id}",
                    "score": candidate.total_score,
                    "rank": rank,
                }
            )

    # 허브(인기) 팀 강조용 — 몇 명의 유저에게 상위 TOP_K_EDGES 안에 매칭됐는지(in-degree)를
    # 세서 노드에 실어 보낸다. 지금까진 모든 노드 크기가 같아 "많이 매칭되는 팀"이 시각적으로
    # 안 보인다는 피드백(2026-08-20)에 대응 — FE가 이 값으로 노드 크기/테두리를 조절할 수 있게
    # 원시 카운트만 넘기고, 실제 스케일링(반지름 공식 등)은 렌더링 쪽 재량으로 남겨둔다.
    match_counts: dict[str, int] = {f"team:{tid}": 0 for tid in team_ids}
    for edge in edges:
        match_counts[edge["target"]] += 1

    nodes = []
    for tid in team_ids:
        x, y = team_coords[tid]
        role = team_roles[tid]
        nodes.append(
            {
                "id": f"team:{tid}",
                "type": "team",
                "role": role,
                "label": f"팀 {tid} ({role})",
                "x": float(x),
                "y": float(y),
                "color": color_map[role],
                "match_count": match_counts[f"team:{tid}"],
            }
        )
    for uid in user_ids:
        x, y = user_coords[uid]
        role = user_roles[uid]
        nodes.append(
            {
                "id": f"user:{uid}",
                "type": "user",
                "role": role,
                "label": f"유저 {uid} ({role})",
                "x": float(x),
                "y": float(y),
                "color": color_map[role],
                "match_count": 0,  # 유저는 엣지의 source일 뿐 target이 아니라 in-degree 개념이 없음
            }
        )

    output = {"nodes": nodes, "edges": edges, "color_map": color_map}
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(nodes)} nodes, {len(edges)} edges to {OUTPUT_PATH}")
    print(f"color_map: {color_map}")


if __name__ == "__main__":
    main()
