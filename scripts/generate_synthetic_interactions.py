"""CF 데모용 합성 상호작용 이력 생성 — **실 사용자 데이터가 아니다.**

목적은 "CF가 점수를 올려준다"를 보이는 게 아니라, **콘텐츠 임베딩이 구조적으로 표현할 수 없는
잠재 구조를 CF만 복원한다**는 걸 보이는 것이다(recovery experiment). 그래서 심는 구조를
아무렇게나 고르지 않고, **실제 공모전 414건의 임베딩으로 분야 중심점 간 거리를 측정해서 가장
먼 쌍**을 골랐다 — 임베딩상 가까운 쌍을 심으면 콘텐츠 기반도 맞힐 수 있어서 아무것도 증명하지
못한다.

심는 구조(측정된 중심점 코사인 유사도):
  - 집단 A 공익 캠페인:    디자인/사진/영상 × 정치/사회/법      (0.777 — 전체에서 가장 먼 쌍)
  - 집단 B 디지털 헬스케어: 의료/보건 × 과학/공학/IT            (0.847)
  - 집단 C 대조군:          콘텐츠 × 기획/아이디어              (0.964 — 가장 가까운 쌍)

집단 C는 "CF가 기존에 잘 되던 걸 망가뜨리지 않는지" 확인하는 대조군이다 — 이 쌍은 임베딩만으로도
이미 연결되므로 CF가 기여할 여지가 거의 없어야 한다.

노이즈 사용자를 섞는 이유: 심은 구조만 있는 데이터는 지나치게 깨끗해서, 실제 희소·잡음 환경에서
동시발생 임계값(min_co_users)이 제 역할을 하는지 볼 수 없다.

출력: data/synthetic_interactions.json — [{"user_id": int, "event_id": int}, ...]
`event_id`는 BE의 정수 ID를 흉내내기 위해 externalId(예: "linkareer-337930")의 숫자 부분을 쓴다.
"""

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
EVENTS_PATH = ROOT / "data" / "result_events.json"
OUTPUT_PATH = ROOT / "data" / "synthetic_interactions.json"
GROUPS_PATH = ROOT / "data" / "synthetic_interaction_groups.json"

SEED = 20260901
USERS_PER_GROUP = 40
NOISE_USERS = 30
PICKS_PER_FIELD = (2, 4)  # 사용자당 각 분야에서 뽑는 공모전 수 범위
NOISE_PICKS = (3, 5)

# (집단 이름, 분야 A, 분야 B, 설명) — 위 docstring의 측정 결과에서 고른 조합
PLANTED_GROUPS = [
    ("A_public_campaign", "DESIGN_PHOTO_ART_VIDEO", "POLITICS_SOCIETY_LAW", "공익 캠페인 관심층"),
    ("B_digital_health", "MEDICAL_HEALTH", "SCIENCE_ENGINEERING_TECH_IT", "디지털 헬스케어 관심층"),
    ("C_control_near", "CONTENTS", "PLANNING_IDEA", "대조군(임베딩상 이미 가까운 쌍)"),
]


def _event_id(external_id: str) -> int:
    return int(external_id.rsplit("-", 1)[-1])


def _events_by_field() -> dict[str, list[int]]:
    rows = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    seen: set[str] = set()
    by_field: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        external_id = row["externalId"]
        field = row.get("field")
        if not field or external_id in seen:
            continue
        seen.add(external_id)
        by_field[field].append(_event_id(external_id))
    return dict(by_field)


def main() -> None:
    rng = random.Random(SEED)
    by_field = _events_by_field()
    all_event_ids = [eid for ids in by_field.values() for eid in ids]

    interactions: list[dict] = []
    group_members: dict[str, list[int]] = {}
    next_user_id = 1

    for name, field_a, field_b, description in PLANTED_GROUPS:
        pool_a, pool_b = by_field.get(field_a, []), by_field.get(field_b, [])
        if not pool_a or not pool_b:
            raise SystemExit(f"분야 데이터 부족: {field_a}({len(pool_a)}) / {field_b}({len(pool_b)})")

        members = []
        for _ in range(USERS_PER_GROUP):
            user_id = next_user_id
            next_user_id += 1
            members.append(user_id)
            # 두 분야에서 각각 뽑아야 **분야를 가로지르는** 동시발생이 생긴다 — 이게 심는 구조다.
            for pool in (pool_a, pool_b):
                count = min(len(pool), rng.randint(*PICKS_PER_FIELD))
                for event_id in rng.sample(pool, count):
                    interactions.append({"user_id": user_id, "event_id": event_id})
        group_members[name] = members
        print(f"{name} ({description}): {USERS_PER_GROUP}명, {field_a} × {field_b}")

    # 노이즈 — 어떤 잠재 구조도 없는 무작위 사용자
    for _ in range(NOISE_USERS):
        user_id = next_user_id
        next_user_id += 1
        count = rng.randint(*NOISE_PICKS)
        for event_id in rng.sample(all_event_ids, count):
            interactions.append({"user_id": user_id, "event_id": event_id})
    print(f"노이즈 사용자: {NOISE_USERS}명 (잠재 구조 없음)")

    OUTPUT_PATH.write_text(
        json.dumps(interactions, ensure_ascii=False), encoding="utf-8"
    )
    GROUPS_PATH.write_text(
        json.dumps(
            {
                "seed": SEED,
                "groups": [
                    {
                        "name": name,
                        "field_a": field_a,
                        "field_b": field_b,
                        "description": description,
                        "user_ids": group_members[name],
                    }
                    for name, field_a, field_b, description in PLANTED_GROUPS
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n상호작용 {len(interactions)}건 / 사용자 {next_user_id - 1}명")
    print(f"저장: {OUTPUT_PATH.relative_to(ROOT)}, {GROUPS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
