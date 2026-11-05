from app.schemas.activity import activity_style_label
from app.schemas.role_codes import role_label
from app.scoring.label_reason import pick_label_reason
from app.scoring.rules import overlap_ratio


def role_match_score(desired_roles: list[str], recruiting_roles: list[str]) -> float:
    # 정확히 같은 역할 코드만 인정한다. 같은 공모전 도메인의 다른 역할에 부분 점수(0.5)를 주는 안은
    # 2026-11-05에 넣었다가 뺐다 — 도메인은 "어느 공모전 분야인가"로 묶은 것이라 BE와 UI/UX 디자인처럼
    # 하는 일이 다른 역할도 같은 도메인이고, 저장소의 평가셋 전부에서 순위 품질이 떨어졌다
    # (LLM 생성 풀 USER_TO_TEAM NDCG@10 0.933→0.904, 1위 정답률 0.98→0.92).
    return overlap_ratio(needed=desired_roles, available=recruiting_roles)


def deficit_fit_score(skills: list[str], required_skills: list[str]) -> float:
    return overlap_ratio(needed=required_skills, available=skills)


# beginner_fit은 "선호"가 아니라 "이 팀이 초보자를 받는가"라는 적합성(eligibility) 신호에
# 가까워서, activity_style_match 같은 순수 취향 신호보다 훨씬 높게 둔다(2026-07-15 확인 —
# 이전 0.075 가중치에서는 유사도·역할·스킬이 전부 만점인 비초보자 팀(0.925)이 유사도만 절반인
# 초보자 친화 팀(0.75)을 이겨, 초보자 1순위 추천에 초보자를 지양하는 팀이 뜨는 사례가 나왔다).
# cf_affinity(item-to-item CF)를 추가하면서 기존 5개를 **균일하게 0.95배로 축소**하고 남은
# 0.05를 배정했다(2026-09-01). 균일 축소를 택한 이유는 두 가지다:
#   (1) 기존 5개의 **상대 비율이 완전히 보존**된다 — 실측으로 튜닝해온 beginner_fit 우위
#       구조(위 주석 참고)가 그대로 유지되고, 기존 평가 수치의 해석도 그대로 유효하다.
#   (2) 동시발생 데이터가 아직 없으면 모든 후보의 cf_affinity가 0이 되고, 그러면 총점이
#       `0.95 × 기존 점수`라는 단조 변환이 되어 **순위가 수학적으로 불변**이다("안전할
#       것이다"가 아니라 증명 가능하게 안전하다 — tests/test_cf_affinity_scoring.py).
# 데이터가 쌓이면 클러스터 lift 메커니즘(app/scoring/cluster_weights.py)이 이 가중치도 함께
# 조정하므로, 0.05라는 초기값을 감으로 계속 튜닝할 필요가 없다.
WEIGHTS = {
    "similarity": 0.38,
    "role_match": 0.19,
    "deficit_fit": 0.1425,
    "beginner_fit": 0.19,
    "activity_style_match": 0.0475,
    "cf_affinity": 0.05,
}

# 후보가 2~3개뿐이면 min-max 정규화가 사소한 원시 유사도 차이도 0~1 최대치로 벌려버려서,
# beginner_fit 가중치(0.2)만으로는 "초보자 비친화" 팀이 유사도 우위로 여전히 이길 수 있었다
# (실측: 거의 동일한 팀 소개 텍스트 두 개 중 "초보자는 정중히 지양합니다"만 다른 팀이
# 0.625점으로 "초보자 환영" 팀 0.425점을 역전, 2026-07-15). beginner_fit이 최악값(0.0)이면
# — 즉 이 팀이 명시적으로 초보자를 받지 않으면 — 총점에 강한 배율을 곱해 순위를 확실히
# 끌어내린다. app/scoring/engine.py의 combine_score 참고.
PENALTY_RULES: dict[str, tuple[float, float]] = {"beginner_fit": (0.0, 0.3)}

_LABELS = {
    "role_match": "희망 역할과 일치해요",
    "deficit_fit": "팀이 필요한 스킬을 갖췄어요",
    "activity_style_match": "활동 방식이 잘 맞아요",
    "beginner_fit": "초보자도 편하게 참여할 수 있어요",
    # CF가 추천을 주도한 경우 그 사실 자체를 사용자에게 드러낸다 — 다른 라벨들이 "무엇이
    # 일치하는가"를 말한다면, 이 라벨은 "왜 당신에게 보이는가"의 근거가 다르다는 걸 밝힌다.
    "cf_affinity": "비슷한 공모전을 찾아본 사람들이 함께 관심을 보인 팀이에요",
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
    # 라벨은 "실제로 맞았다"는 점수만 근거로 삼는다(app/scoring/label_reason.py). 초보자 라벨은
    # 초보 사용자 × 초보 환영 팀일 때만 — 초보자가 아니거나 경험 수준을 모르면(None) beginner_fit
    # 1.0은 "해당 없음"이다(beginner_fit_score도 모르는 경우를 비초보자로 취급한다).
    beginner_relevant = beginner_friendly is True and seeker_is_beginner is True
    reason = pick_label_reason(metadata_scores, beginner_relevant=beginner_relevant)
    if reason is None:
        return "의미적으로 관심사가 잘 맞아요"

    # 역할·활동 방식은 코드 값("COOK_WESTERN", "ONLINE")이 아니라 한글 라벨로 보여준다.
    if reason == "role_match" and matched_roles:
        return f"{', '.join(role_label(r) for r in matched_roles)} 역할을 모집하고 있어요"
    if reason == "deficit_fit" and matched_skills:
        return f"{', '.join(matched_skills)} 스킬이 필요한 팀이에요"
    if reason == "activity_style_match" and activity_style:
        return f"'{activity_style_label(activity_style)}' 방식으로 활동해요"
    if reason == "beginner_fit":
        return "초보자도 편하게 참여할 수 있는 팀이에요"

    return _LABELS.get(reason, "적합한 팀이에요")
