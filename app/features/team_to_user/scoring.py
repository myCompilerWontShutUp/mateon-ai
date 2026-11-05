from app.schemas.activity import activity_style_label
from app.schemas.role_codes import role_label
from app.scoring.label_reason import pick_label_reason
from app.scoring.rules import overlap_ratio


def role_match_score(recruiting_roles: list[str], desired_roles: list[str]) -> float:
    # USER_TO_TEAM과 같은 규칙 — 정확히 같은 역할 코드만 인정한다(부분 점수를 뺀 이유는
    # app/features/user_to_team/scoring.py의 role_match_score 주석 참고).
    return overlap_ratio(needed=recruiting_roles, available=desired_roles)


def deficit_fit_score(required_skills: list[str], skills: list[str]) -> float:
    return overlap_ratio(needed=required_skills, available=skills)


# 제안(USER_TO_TEAM)과 동일한 가중치/구성요소 — 역할 일치도/결핍 보완도/활동 방식 일치도/초보자
# 적합도는 방향과 무관한 대칭적 호환성 체크라서 로직을 뒤집지 않고 그대로 재사용한다.
# portfolio_role_fit(옛 experience_level 대리 지표)은 실제 신호가 약해 계산에서 뺐다 —
# 협업 온도와 같은 취급으로, 실제 포트폴리오 데이터가 생기면 다시 넣는다
# (`ProposalSchema.portfolio_role_fit_score` 필드는 그대로 예약해둔다).
# cf_affinity 추가에 따른 0.95 균일 축소도 양방향 동일하게 적용한다 — 근거는
# app/features/user_to_team/scoring.py의 WEIGHTS 주석 참고. 이 방향에서는 후보(사용자)의
# `interacted_event_ids`와 팀이 속한 공모전 사이의 동시발생을 본다(계산 함수는
# app/scoring/cooccurrence.py를 양방향이 그대로 공유한다).
WEIGHTS = {
    "similarity": 0.38,
    "role_match": 0.19,
    "deficit_fit": 0.1425,
    "beginner_fit": 0.19,
    "activity_style_match": 0.0475,
    "cf_affinity": 0.05,
}

# USER_TO_TEAM과 동일한 이유로 동일하게 적용한다 — app/features/user_to_team/scoring.py의
# PENALTY_RULES 주석 참고.
PENALTY_RULES: dict[str, tuple[float, float]] = {"beginner_fit": (0.0, 0.3)}

_LABELS = {
    "role_match": "팀의 결핍 역할과 일치해요",
    "deficit_fit": "팀이 필요한 스킬을 갖췄어요",
    "activity_style_match": "활동 방식이 잘 맞아요",
    "beginner_fit": "초보자도 편하게 참여할 수 있어요",
    # USER_TO_TEAM 쪽과 대칭 — CF가 근거일 때 그 사실을 라벨로 드러낸다.
    "cf_affinity": "이 공모전과 함께 주목받는 활동에 관심을 보인 분이에요",
}


def label_for(
    metadata_scores: dict[str, float],
    *,
    matched_roles: list[str] | None = None,
    matched_skills: list[str] | None = None,
    activity_style: str | None = None,
    beginner_friendly: bool | None = None,
    seeker_is_beginner: bool | None = None,
) -> str:
    # USER_TO_TEAM과 같은 근거 규칙(app/scoring/label_reason.py). 여기서 seeker는 후보 사용자다 —
    # 초보 후보 × 초보 환영 팀일 때만 초보자 라벨을 쓴다(경험 수준을 모르면 쓰지 않는다).
    beginner_relevant = beginner_friendly is True and seeker_is_beginner is True
    reason = pick_label_reason(metadata_scores, beginner_relevant=beginner_relevant)
    if reason is None:
        return "의미적으로 결핍과 잘 맞아요"

    # 역할·활동 방식은 코드 값이 아니라 한글 라벨로 보여준다(USER_TO_TEAM 쪽과 동일).
    if reason == "role_match" and matched_roles:
        return f"{', '.join(role_label(r) for r in matched_roles)} 역할에 지원 가능해요"
    if reason == "deficit_fit" and matched_skills:
        return f"{', '.join(matched_skills)} 스킬을 갖췄어요"
    if reason == "activity_style_match" and activity_style:
        return f"'{activity_style_label(activity_style)}' 방식으로 활동해요"
    if reason == "beginner_fit":
        return "초보자도 편하게 합류할 수 있어요"

    return _LABELS.get(reason, "이 팀에 적합해요")
