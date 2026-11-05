"""item-to-item 협업 필터링(CF) — 공모전 단위 동시발생 계산.

**이 모듈이 이 저장소에서 유일하게 진짜 협업 신호를 다루는 곳이다.** 임베딩 기반 유사도
(`similarity`)나 행동 임베딩 블렌딩(`behavior_blend.py`)은 전부 콘텐츠 기반이라, 다른
사용자의 행동이 개입하지 않는다 — 최근 연구가 반복해서 지적하는 "의미 임베딩은 CF 신호를
인코딩하지 못한다"는 한계가 그대로 적용된다. 여기서는 반대로 **텍스트를 전혀 보지 않고**
"같은 사람들이 무엇을 함께 봤는가"만으로 공모전 간 연관도를 만든다.

방식은 Amazon이 1998년부터 써온 고전적인 item-to-item CF와 같다 — 사용자별 상호작용
목록에서 공모전 쌍의 동시발생을 세고, 인기 편향을 없애기 위해 코사인으로 정규화한다:

    sim(a, b) = |users(a) ∩ users(b)| / sqrt(|users(a)| · |users(b)|)

분모의 정규화가 없으면 단순히 인기 많은 공모전이 모든 것과 연관돼 보이는 문제가 생긴다.
결과는 항상 [0, 1] 범위라 다른 컴포넌트 점수와 같은 스케일로 바로 결합할 수 있다.

**팀이 아니라 공모전 단위로 계산하는 이유**: 팀은 모집이 끝나면 사라져서 상호작용이 누적될
시간 자체가 없다(구조적으로 CF가 성립 불가). 반면 공모전은 오래 남고 여러 사용자가 같은
공모전을 본다 — 실제로 행렬이 만들어지는 유일한 축이다.
"""

import math
from collections import defaultdict

# 이 미만으로 겹치는 쌍은 우연일 가능성이 커서 버린다(희소 데이터에서의 최소 방어).
DEFAULT_MIN_CO_USERS = 2


def build_cooccurrence(
    interactions: list[dict],
    min_co_users: int = DEFAULT_MIN_CO_USERS,
) -> dict[int, dict[int, float]]:
    """상호작용 이력에서 공모전 간 동시발생 행렬을 만든다(오프라인 배치 전용).

    interaction 형태: {"user_id": int, "event_id": int}
    (같은 쌍이 여러 번 나와도 사용자당 1회로 취급한다 — 북마크와 지원을 둘 다 한 경우
    가중치가 두 배가 되는 걸 막기 위함이다. 상호작용 종류별 가중치는 지금 두지 않는다.)

    반환: {event_id: {other_event_id: 유사도}} — 대칭 행렬이라 양방향 모두 채운다.
    """
    users_by_event: dict[int, set[int]] = defaultdict(set)
    for row in interactions:
        users_by_event[row["event_id"]].add(row["user_id"])

    result: dict[int, dict[int, float]] = defaultdict(dict)
    event_ids = sorted(users_by_event)
    for i, event_a in enumerate(event_ids):
        users_a = users_by_event[event_a]
        for event_b in event_ids[i + 1 :]:
            users_b = users_by_event[event_b]
            shared = len(users_a & users_b)
            if shared < min_co_users:
                continue

            similarity = shared / math.sqrt(len(users_a) * len(users_b))
            result[event_a][event_b] = similarity
            result[event_b][event_a] = similarity

    return dict(result)


def as_event_id(value) -> int | None:
    """요청 metadata는 자유 dict라 공모전 ID가 "337930" 같은 문자열로 올 수도 있다. 저장소의 키는
    정수라 그대로 비교하면 조용히 0점이 되므로 정수로 맞춘다. 정수로 못 바꾸는 값은 None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_event_ids(values) -> list[int]:
    if not isinstance(values, (list, tuple, set)):
        return []
    return [event_id for event_id in (as_event_id(v) for v in values) if event_id is not None]


def cooccurrence_affinity(
    source_event_ids: list[int],
    target_event_id: int | None,
    cooccurrence: dict[int, dict[int, float]],
) -> float:
    """기준 공모전들과 상대 공모전 사이의 협업 연관도를 [0, 1]로 돌려준다.

    - USER_TO_TEAM: source = 사용자가 상호작용한 공모전들, target = 후보 팀이 속한 공모전
    - TEAM_TO_USER: source = 후보 사용자가 상호작용한 공모전들, target = 팀이 속한 공모전

    여러 값 중 **평균이 아니라 최댓값**을 쓴다 — "당신이 관심을 보인 것들 중 하나와 강하게
    연결돼 있다"가 CF가 실제로 잡아내려는 신호이고, 평균을 쓰면 관심사가 넓은 사용자일수록
    모든 후보의 점수가 함께 희석돼 변별력이 사라진다(Amazon의 item-to-item도 같은 이유로
    각 아이템의 유사 아이템을 모아 결합한다).

    데이터가 없으면(저장소가 비었거나 처음 보는 공모전) 0.0 — 이때 모든 후보가 같은 값을
    받으므로 순위에 영향을 주지 않는다.
    """
    target = as_event_id(target_event_id)
    sources = as_event_ids(source_event_ids)
    if target is None or not sources or not cooccurrence:
        return 0.0

    neighbors = cooccurrence.get(target)
    if not neighbors:
        return 0.0

    # 자기 자신은 제외한다 — 이미 본 공모전의 팀을 "연관도 1.0"으로 최상단에 올리는 건
    # 추천이 아니라 되풀이다.
    scores = [neighbors.get(source_id, 0.0) for source_id in sources if source_id != target]
    return max(scores, default=0.0)
