from app.scoring.rules import overlap_ratio


def role_match_score(recruiting_roles: list[str], desired_roles: list[str]) -> float:
    return overlap_ratio(needed=recruiting_roles, available=desired_roles)


def deficit_fit_score(required_skills: list[str], skills: list[str]) -> float:
    return overlap_ratio(needed=required_skills, available=skills)


# 제안(USER_TO_TEAM)과 동일한 가중치/구성요소 — 역할 일치도/결핍 보완도/활동 방식 일치도/초보자
# 적합도는 방향과 무관한 대칭적 호환성 체크라서 로직을 뒤집지 않고 그대로 재사용한다.
# portfolio_role_fit(옛 experience_level 대리 지표)은 실제 신호가 약해 계산에서 뺐다 —
# 협업 온도와 같은 취급으로, 실제 포트폴리오 데이터가 생기면 다시 넣는다
# (`ProposalSchema.portfolio_role_fit_score` 필드는 그대로 예약해둔다).
WEIGHTS = {
    "similarity": 0.5,
    "role_match": 0.2,
    "deficit_fit": 0.15,
    "activity_style_match": 0.075,
    "beginner_fit": 0.075,
}

_LABELS = {
    "role_match": "팀의 결핍 역할과 일치해요",
    "deficit_fit": "팀이 필요한 스킬을 갖췄어요",
    "activity_style_match": "활동 방식이 잘 맞아요",
    "beginner_fit": "초보자도 편하게 참여할 수 있어요",
}


def label_for(metadata_scores: dict[str, float]) -> str:
    top = max(metadata_scores, key=metadata_scores.get)
    return _LABELS.get(top, "이 팀에 적합해요")
