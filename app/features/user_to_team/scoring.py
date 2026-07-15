from app.scoring.rules import overlap_ratio


def role_match_score(desired_roles: list[str], recruiting_roles: list[str]) -> float:
    return overlap_ratio(needed=desired_roles, available=recruiting_roles)


def deficit_fit_score(skills: list[str], required_skills: list[str]) -> float:
    return overlap_ratio(needed=required_skills, available=skills)


WEIGHTS = {
    "similarity": 0.5,
    "role_match": 0.2,
    "deficit_fit": 0.15,
    "activity_style_match": 0.075,
    "beginner_fit": 0.075,
}

_LABELS = {
    "role_match": "희망 역할과 일치해요",
    "deficit_fit": "팀이 필요한 스킬을 갖췄어요",
    "activity_style_match": "활동 방식이 잘 맞아요",
    "beginner_fit": "초보자도 편하게 참여할 수 있어요",
}


def label_for(metadata_scores: dict[str, float]) -> str:
    top = max(metadata_scores, key=metadata_scores.get)
    return _LABELS.get(top, "적합한 팀이에요")
