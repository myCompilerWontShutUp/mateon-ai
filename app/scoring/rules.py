def overlap_ratio(needed: list[str], available: list[str]) -> float:
    if not needed or not available:
        return 0.0
    needed_set = {n.lower() for n in needed}
    available_set = {a.lower() for a in available}
    return len(needed_set & available_set) / len(needed_set)


def matched_items(needed: list[str], available: list[str]) -> list[str]:
    available_lower = {a.lower() for a in available}
    return [n for n in needed if n.lower() in available_lower]


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


# 선택 필드(activity_time)용 매칭 신호 — activity_style_match_score와 동일한 계산이지만
# 기본 WEIGHTS에는 포함되지 않는다(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 4번). 클러스터
# 가산점(1번 항목)이 실 데이터로 이 컴포넌트가 유의미하다고 판단하기 전까지는 계산만 해서
# component_scores로 노출할 뿐 total_score에는 영향을 주지 않는다.
def activity_time_match_score(time_a: str | None, time_b: str | None) -> float:
    if not time_a or not time_b:
        return 0.5
    return 1.0 if time_a.strip().lower() == time_b.strip().lower() else 0.0
