def overlap_ratio(needed: list[str], available: list[str]) -> float:
    if not needed or not available:
        return 0.0
    needed_set = {n.lower() for n in needed}
    available_set = {a.lower() for a in available}
    return len(needed_set & available_set) / len(needed_set)


# 활동 방식 일치도/초보자 적합도는 "누가 누구를 보는가"와 무관한 대칭적 호환성 체크라서
# USER_TO_TEAM/TEAM_TO_USER 양쪽에서 인자만 맞춰 그대로 재사용한다.


def activity_style_match_score(style_a: str | None, style_b: str | None) -> float:
    if not style_a or not style_b:
        return 0.5
    return 1.0 if style_a.strip().lower() == style_b.strip().lower() else 0.0


def beginner_fit_score(experience_level: str | None, beginner_friendly: bool | None) -> float:
    if experience_level != "beginner":
        return 1.0
    if beginner_friendly is None:
        return 0.5
    return 1.0 if beginner_friendly else 0.0
