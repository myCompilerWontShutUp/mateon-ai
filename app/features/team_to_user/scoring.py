from app.scoring.rules import overlap_ratio

_EXPERIENCE_LEVEL_READINESS = {"advanced": 1.0, "intermediate": 0.6, "beginner": 0.3}


def role_match_score(recruiting_roles: list[str], desired_roles: list[str]) -> float:
    return overlap_ratio(needed=recruiting_roles, available=desired_roles)


def deficit_fit_score(required_skills: list[str], skills: list[str]) -> float:
    return overlap_ratio(needed=required_skills, available=skills)


def portfolio_role_fit_score(experience_level: str | None) -> float:
    # 포트폴리오 데이터가 아직 스키마에 없어 experience_level을 "이 역할에 대한 실무 준비도"의
    # 대리 지표로 쓴다 — 백엔드에 실제 포트폴리오 데이터 소스가 생기면 교체해야 한다.
    if experience_level is None:
        return 0.5
    return _EXPERIENCE_LEVEL_READINESS.get(experience_level, 0.5)


def activity_goal_match_score(team_goal: str | None, candidate_goal: str | None) -> float:
    if not team_goal or not candidate_goal:
        return 0.5
    return 1.0 if team_goal.strip().lower() == candidate_goal.strip().lower() else 0.0


WEIGHTS = {
    "similarity": 0.3,
    "role_match": 0.25,
    "deficit_fit": 0.2,
    "portfolio_role_fit": 0.15,
    "activity_goal_match": 0.1,
}

_LABELS = {
    "role_match": "팀의 결핍 역할과 일치해요",
    "deficit_fit": "팀이 필요한 스킬을 갖췄어요",
    "portfolio_role_fit": "이 역할에 대한 준비도가 높아요",
    "activity_goal_match": "활동 목표가 잘 맞아요",
}


def label_for(metadata_scores: dict[str, float]) -> str:
    top = max(metadata_scores, key=metadata_scores.get)
    return _LABELS.get(top, "이 팀에 적합해요")
