"""추천 목록의 짧은 라벨이 어떤 점수 구성요소를 근거로 삼을지 고른다.

점수는 "맞지 않는다는 근거가 없음"도 높은 값으로 표현한다 — 초보자가 아닌 사용자의 beginner_fit은
"해당 없음"이라 1.0이고, 한쪽 활동 방식을 모르면 activity_style_match는 중립값 0.5다. 그런 값을 그대로
라벨 근거로 쓰면 초보자를 받지 않는 팀에도 "초보자도 편하게 참여할 수 있어요"가 붙었다(2026-11-05
확인, 평가 데이터 Top10 항목의 3%). 그래서 라벨은 "실제로 맞았다"는 뜻의 점수만 근거로 삼는다.
"""

# 점수가 같을 때 먼저 고를 순서 — 구체적인 일치(역할·스킬)를 일반적인 일치보다 앞에 둔다.
REASON_PRIORITY: tuple[str, ...] = (
    "role_match",
    "deficit_fit",
    "cf_affinity",
    "activity_style_match",
    "beginner_fit",
)


def pick_label_reason(metadata_scores: dict[str, float], *, beginner_relevant: bool) -> str | None:
    """라벨 근거로 쓸 구성요소 이름. 근거가 하나도 없으면 None.

    - activity_style_match: 정확히 일치(1.0)할 때만. 0.5는 한쪽 정보가 없다는 뜻이다.
    - beginner_fit: 초보자와 초보 환영 팀이 만났을 때만(beginner_relevant). 그 밖의 1.0은 "해당 없음"이다.
    - 나머지: 0보다 크면.
    가장 높은 점수를 고르고, 같으면 REASON_PRIORITY 순서를 따른다.
    """
    best: tuple[float, int, str] | None = None
    for order, name in enumerate(REASON_PRIORITY):
        score = metadata_scores.get(name)
        if score is None or score <= 0:
            continue
        if name == "activity_style_match" and score < 1.0:
            continue
        if name == "beginner_fit" and not beginner_relevant:
            continue
        candidate = (score, -order, name)
        if best is None or candidate > best:
            best = candidate
    return best[2] if best else None
