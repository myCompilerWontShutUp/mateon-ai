from app.scoring.rules import overlap_ratio


def role_match_score(desired_roles: list[str], recruiting_roles: list[str]) -> float:
    return overlap_ratio(needed=desired_roles, available=recruiting_roles)


def deficit_fit_score(skills: list[str], required_skills: list[str]) -> float:
    return overlap_ratio(needed=required_skills, available=skills)


# beginner_fit은 "선호"가 아니라 "이 팀이 초보자를 받는가"라는 적합성(eligibility) 신호에
# 가까워서, activity_style_match 같은 순수 취향 신호보다 훨씬 높게 둔다(2026-07-15 확인 —
# 이전 0.075 가중치에서는 유사도·역할·스킬이 전부 만점인 비초보자 팀(0.925)이 유사도만 절반인
# 초보자 친화 팀(0.75)을 이겨, 초보자 1순위 추천에 초보자를 지양하는 팀이 뜨는 사례가 나왔다).
WEIGHTS = {
    "similarity": 0.4,
    "role_match": 0.2,
    "deficit_fit": 0.15,
    "beginner_fit": 0.2,
    "activity_style_match": 0.05,
}

_LABELS = {
    "role_match": "희망 역할과 일치해요",
    "deficit_fit": "팀이 필요한 스킬을 갖췄어요",
    "activity_style_match": "활동 방식이 잘 맞아요",
    "beginner_fit": "초보자도 편하게 참여할 수 있어요",
}


def label_for(
    metadata_scores: dict[str, float],
    *,
    matched_roles: list[str] | None = None,
    matched_skills: list[str] | None = None,
    activity_style: str | None = None,
    beginner_friendly: bool | None = None,
) -> str:
    top = max(metadata_scores, key=metadata_scores.get)
    if metadata_scores[top] <= 0:
        return "의미적으로 관심사가 잘 맞아요"

    if top == "role_match" and matched_roles:
        return f"{', '.join(matched_roles)} 역할을 모집하고 있어요"
    if top == "deficit_fit" and matched_skills:
        return f"{', '.join(matched_skills)} 스킬이 필요한 팀이에요"
    if top == "activity_style_match" and activity_style:
        return f"'{activity_style}' 방식으로 활동해요"
    if top == "beginner_fit" and beginner_friendly:
        return "초보자도 편하게 참여할 수 있는 팀이에요"

    return _LABELS.get(top, "적합한 팀이에요")
