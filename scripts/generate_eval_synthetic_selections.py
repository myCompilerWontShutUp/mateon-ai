"""1번 항목(오프라인 클러스터 가중치 재계산 배치)의 알고리즘을 시연하기 위해, 실제
`cluster_selection_events` 대신 합성 선택 이벤트를 만들어 같은 알고리즘(`compute_weight_lifts`)을
돌린다. 이 파일 자체가 만드는 데이터는 실 서비스 신호가 아니다 — BE 연동이 실제로 시작되기
전까지 2번 항목(Hit@10 평가)의 "보정모델" 비교군에 넣을 값을 얻기 위한 시뮬레이션이다
(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 참고, 2026-08-20 결정).

**시뮬레이션 방식(2026-08-20 수정)**: 처음엔 "정답 팀들 중 프로덕션(비교군 2) 점수가 가장 높은
팀을 선택했다"고 가정했는데, 이러면 보정 알고리즘이 프로덕션 스코어링이 이미 잘하고 있는 것만
재확인할 뿐 프로덕션의 약점을 찾아내지 못한다(순환 논리) — 실제로 돌려보니 비교군 3이 비교군
2보다 오히려 낮게 나와서 발견했다. 대신 여기서는 **"실제 사용자 선호가 현재 가중치와는 다르게,
활동 방식 일치도·초보자 적합도를 더 중시한다"는 가상의 시나리오**를 시뮬레이션한다 — 정답 팀들
중 이 대체 가중치(`_SIMULATED_TRUE_PREFERENCE_WEIGHTS`) 기준 점수가 가장 높은 팀을 "선택됐다"고
가정한다. 프로덕션 가중치와 의도적으로 다르게 설계했으므로 보정 알고리즘이 실제로 그 격차를
찾아내 회복하는지 검증할 수 있다 — 실 데이터가 아니라 예시 시나리오라는 점은 변하지 않는다.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation.scoring_arms import production_ranking  # noqa: E402
from app.evaluation.simulation import true_preference_score  # noqa: E402
from app.scoring.cluster import user_cluster_key  # noqa: E402
from app.scoring.cluster_weights import compute_weight_lifts  # noqa: E402

TEAMS_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_teams.json"
USERS_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_users.json"
GROUND_TRUTH_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_ground_truth.json"
EVENTS_OUTPUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_synthetic_selections.json"
LIFTS_OUTPUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "eval_cluster_weight_lifts.json"

_COMPONENTS = ["similarity", "role_match", "deficit_fit", "beginner_fit", "activity_style_match"]


def main() -> None:
    teams = json.loads(TEAMS_PATH.read_text(encoding="utf-8"))
    users = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))

    events = []
    skipped = 0
    for user_id, user in users.items():
        relevant_ids = set(ground_truth.get(user_id, {}).get("relevant_team_ids", []))
        if not relevant_ids:
            skipped += 1
            continue

        ranked = production_ranking(user["embedding_vector"], user["metadata"], teams)
        shown_candidates = [
            {
                "candidate_id": c.candidate_id,
                "total_score": c.total_score,
                "component_scores": {"similarity": c.similarity, **c.metadata_scores},
            }
            for c in ranked
        ]
        # 정답 팀들 중 "진짜 사용자 선호"(대체 가중치) 기준 점수가 가장 높은 걸 "선택됨"으로
        # 시뮬레이션한다 — 프로덕션 점수 기준이 아니다(위 모듈 docstring 참고).
        selected = max(
            (c for c in ranked if c.candidate_id in relevant_ids), key=true_preference_score
        )

        cluster_key = user_cluster_key(
            user["metadata"].get("desired_roles", []), user["metadata"].get("experience_level")
        )
        events.append(
            {
                "chooser_cluster_key": cluster_key,
                "selected_candidate_id": selected.candidate_id,
                "shown_candidates": shown_candidates,
            }
        )

    EVENTS_OUTPUT.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(events)} synthetic selection events to {EVENTS_OUTPUT} ({skipped}명 정답 없어 제외)")

    lifts = compute_weight_lifts(events, components=_COMPONENTS)
    LIFTS_OUTPUT.write_text(json.dumps(lifts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"computed weight lifts for {len(lifts)} clusters -> {LIFTS_OUTPUT}")
    for cluster_key, lift in lifts.items():
        print(f"  {cluster_key}: {lift}")


if __name__ == "__main__":
    main()
