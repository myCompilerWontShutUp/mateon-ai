"""⑤ 비교군 — mateon-backend의 기존 룰베이스 매칭을 그대로 옮긴 것.

원본: `mateon-backend/src/main/java/com/example/mateon/events/service/EventMatchingService.java`의
`calculateRelevanceScore` / `matchInterestJob`. 흉내가 아니라 **동작을 한 줄씩 대응시켜 옮겼다**
— "룰베이스보다 낫다"는 주장을 하려면 비교 대상이 허수아비여서는 안 되기 때문이다.

원본 동작:
- 사용자의 희망직무 1·2·3순위(30·20·10점)를 각각 대상 텍스트에서 찾는다.
- 희망직무 문자열이 대상 텍스트에 **통째로 들어 있으면** 만점.
- 아니면 공백으로 쪼갠 토큰 중 **2글자 이상이면서 대상 텍스트에 들어 있는 토큰 수**에 비례해
  부분 점수(`base * 일치 토큰 수 / 전체 토큰 수`, Java 정수 나눗셈).
- 대소문자는 무시하고, 비교는 전부 부분 문자열(`contains`)이다 — 그래서 "AI"가 "email"에
  걸리고 "서버 운영자"는 "백엔드 개발자"를 못 찾는다(원본 코드 주석에 기록된 한계).

원본에서 옮기지 않은 축: 대학교·전공·단과대·캠퍼스 가산점. 평가 데이터의 사용자·팀 어느 쪽에도
그 정보가 없어 모든 후보가 똑같이 0점을 받으므로, 빼도 순위가 달라지지 않는다.

팀 매칭에 맞춘 대응(원본은 사용자↔공모전 매칭이다):
- 대상 텍스트: 원본은 공모전 `제목+설명+요약`을 이어붙인다. 여기서는 팀 모집글 원문 + 모집 역할의
  한글 표기 + 요구 스킬을 이어붙인다(백엔드가 `Team.role`을 한글 자유 텍스트로 저장하므로).
- 희망직무: 실제 프로필 화면에는 희망직무 칸이 없고 가장 가까운 게 "키워드(기술스택/관심분야)"
  칸이다. 키워드가 있으면 앞 3개를 1·2·3순위로 쓰고, **비어 있으면 기술분야를 구분자로 잘라
  앞 3개를 쓴다** — 원본 시스템에 가장 유리한 가정이다(키워드가 없을 때 0점으로 두면 기존
  방식을 부당하게 깎아내리는 셈이 된다).
"""

import random
import re

from app.schemas.role_codes import ROLE_CODE_LABELS, RoleCode

SCORE_INTEREST_JOB_PRIMARY = 30
SCORE_INTEREST_JOB_SECONDARY = 20
SCORE_INTEREST_JOB_TERTIARY = 10
_INTEREST_JOB_SCORES = (
    SCORE_INTEREST_JOB_PRIMARY,
    SCORE_INTEREST_JOB_SECONDARY,
    SCORE_INTEREST_JOB_TERTIARY,
)


def match_interest_job(interest_job: str | None, search_text: str, base_score: int) -> int:
    """`EventMatchingService.matchInterestJob`과 동일한 계산."""
    if interest_job is None or not interest_job.strip():
        return 0

    text = search_text.lower().strip()
    job = interest_job.lower().strip()

    if job in text:
        return base_score

    keywords = job.split()  # Java: text.trim().split("\\s+")
    match_count = sum(1 for keyword in keywords if len(keyword) >= 2 and keyword in text)
    if match_count > 0:
        return (base_score * match_count) // len(keywords)  # Java 정수 나눗셈(양수라 내림과 같음)
    return 0


def legacy_relevance_score(interest_jobs: list[str], search_text: str) -> int:
    """`calculateRelevanceScore`의 희망직무 축 — 1·2·3순위를 30·20·10점으로 합산한다."""
    return sum(
        match_interest_job(job, search_text, base)
        for job, base in zip(interest_jobs, _INTEREST_JOB_SCORES, strict=False)
    )


_TECH_FIELD_SEPARATORS = re.compile(r"[,·/\n|]")


def interest_jobs_from_profile(keywords: list[str], tech_field: str) -> list[str]:
    """프로필 화면 입력에서 원본 시스템이 쓸 희망직무 1·2·3순위를 만든다(모듈 docstring 참고)."""
    cleaned_keywords = [k.strip().lstrip("#") for k in keywords if k and k.strip().lstrip("#")]
    if cleaned_keywords:
        return cleaned_keywords[:3]

    parts = []
    for raw in _TECH_FIELD_SEPARATORS.split(tech_field or ""):
        part = raw.strip().strip("-[]").strip()
        if part:
            parts.append(part)
    return parts[:3]


def team_search_text(intro_text: str, recruiting_roles: list[str], required_skills: list[str]) -> str:
    """팀 쪽 대상 텍스트 — 모집글 원문 + 모집 역할 한글 표기 + 요구 스킬."""
    role_labels = []
    for code in recruiting_roles:
        try:
            role_labels.append(ROLE_CODE_LABELS[RoleCode(code)])
        except ValueError:
            role_labels.append(code)
    return " ".join([intro_text, " ".join(role_labels), " ".join(required_skills)])


def legacy_rule_ranking(
    interest_jobs: list[str], team_texts: dict[int, str], tie_break_seed: int
) -> tuple[list[int], dict[int, int]]:
    """점수 내림차순으로 팀을 정렬한다.

    원본은 정렬 기준이 점수뿐이라 동점 처리 규칙이 없다. 동점을 team_id 순으로 두면 "번호가 작은
    팀이 항상 이기는" 체계적 편향이 생기므로, 사용자마다 고정 시드로 섞은 순서로 동점을 가른다
    (재현 가능하면서 특정 팀에 유리하지 않다). 희망직무가 하나도 안 걸리는 사용자는 결국 이
    무작위 순서가 그대로 추천이 된다 — 원본 시스템이 실제로 그렇게 동작한다.
    """
    scores = {team_id: legacy_relevance_score(interest_jobs, text) for team_id, text in team_texts.items()}
    order = list(team_texts)
    random.Random(tie_break_seed).shuffle(order)
    tie_rank = {team_id: position for position, team_id in enumerate(order)}
    ranked = sorted(team_texts, key=lambda team_id: (-scores[team_id], tie_rank[team_id]))
    return ranked, scores
