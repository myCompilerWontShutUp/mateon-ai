"""Hit@10/NDCG 평가(2번 항목)용 팀 50개·유저 50개를 결정론적으로 생성한다.

`tests/fixtures/team_definitions.py`/`user_intent_definitions.py`(기능 테스트용, LLM 추출
파이프라인까지 거침)와 달리, 여기서는 구조화 필드를 직접 만들고 임베딩 텍스트는 곧바로
템플릿으로 렌더링한다 — 평가 목적이 "추출 정확도"가 아니라 "이미 구조화된 정보가 주어졌을 때
랭킹 방법들의 성능 비교"이기 때문에, 추출 단계를 거칠 이유가 없다(비용도 절약된다). 시드
고정으로 재실행해도 항상 같은 fixture가 나온다.
"""

import random

from app.schemas.contest import ContestField
from app.schemas.role_codes import ExperienceLevel, RoleCode
from app.schemas.team_extraction import TeamEmbeddingRefreshRequest, TeamSoftFields
from app.schemas.user_intent import UserIntentFields

_SEED = 20260820
_NUM_TEAMS = 50
_NUM_USERS = 50

_SKILL_POOL: dict[RoleCode, list[str]] = {
    RoleCode.BE: ["Spring Boot", "Node.js", "Django", "FastAPI", "PostgreSQL", "MongoDB", "Kafka", "Redis", "AWS"],
    RoleCode.FE: ["React", "TypeScript", "Vue", "Next.js", "HTML", "CSS", "JavaScript"],
    RoleCode.DESIGN: ["Figma", "Photoshop", "Illustrator", "UI/UX", "Sketch"],
    RoleCode.PM: ["기획", "일정관리", "Notion", "Jira"],
    RoleCode.DATA: ["Python", "Pandas", "scikit-learn", "SQL", "Tableau"],
    RoleCode.MARKETING: ["SNS 마케팅", "콘텐츠 기획", "그로스해킹"],
    RoleCode.CONTENT: ["글쓰기", "영상 편집", "카피라이팅"],
    RoleCode.BUSINESS: ["사업계획서", "재무모델링", "제휴협상"],
    RoleCode.RESEARCH: ["논문 조사", "설문 설계", "통계 분석"],
    RoleCode.ETC: ["일반 업무", "행정"],
}

_DOMAINS = [
    "커머스", "헬스케어", "에듀테크", "핀테크", "여행", "반려동물", "채용", "환경", "부동산",
    "중고거래", "배달", "스포츠", "뷰티", "육아", "푸드테크", "모빌리티", "게임", "예술",
    "음악", "독서", "취미공유", "자원봉사", "재테크", "언어학습", "정신건강",
]

_ACTIVITY_STYLES = ["온라인", "오프라인", "혼합"]
_ACTIVITY_INTENSITIES = ["주 1회", "주 2~3회", "주 4회 이상"]
_ACTIVITY_GOALS = ["공모전 수상", "포트폴리오 제작", "취미로 가볍게", "실무형 프로젝트 경험"]


def _pick_roles(rng: random.Random, n: int) -> list[RoleCode]:
    return rng.sample(list(RoleCode), k=n)


def generate_team_pool() -> dict[int, tuple[TeamEmbeddingRefreshRequest, TeamSoftFields]]:
    rng = random.Random(_SEED)
    teams: dict[int, tuple[TeamEmbeddingRefreshRequest, TeamSoftFields]] = {}

    for team_id in range(1, _NUM_TEAMS + 1):
        recruiting_roles = _pick_roles(rng, rng.choice([1, 1, 2]))
        skills: list[str] = []
        for role in recruiting_roles:
            skills.extend(rng.sample(_SKILL_POOL[role], k=min(2, len(_SKILL_POOL[role]))))

        domain = rng.choice(_DOMAINS)
        activity_style = rng.choice(_ACTIVITY_STYLES)
        activity_intensity = rng.choice(_ACTIVITY_INTENSITIES)
        activity_goal = rng.choice(_ACTIVITY_GOALS)
        beginner_friendly = rng.choices([True, False, None], weights=[4, 4, 2])[0]
        contest_field = rng.choice([*list(ContestField), None, None])  # ~1/(21+2) None 비중

        beginner_phrase = (
            "초보자도 편하게 참여할 수 있는 분위기입니다."
            if beginner_friendly
            else "실무 경험자 위주로 빠르게 진행합니다."
            if beginner_friendly is False
            else ""
        )
        intro_text = (
            f"{domain} 서비스를 만드는 팀입니다. {', '.join(r.value for r in recruiting_roles)} "
            f"역할을 모집 중이며, {activity_style}으로 {activity_intensity} 모입니다. "
            f"{activity_goal}이 목표입니다. {beginner_phrase}"
        ).strip()

        request = TeamEmbeddingRefreshRequest(
            intro_text=intro_text,
            recruiting_roles=[r.value for r in recruiting_roles],
            required_skills=skills,
            contest_field=contest_field.value if contest_field else None,
        )
        soft_fields = TeamSoftFields(
            activity_goal=activity_goal,
            activity_style=activity_style,
            activity_intensity=activity_intensity,
            beginner_friendly=beginner_friendly,
            team_atmosphere="화기애애함" if beginner_friendly else "몰입형",
            recruiting_roles=recruiting_roles,
            contest_field=contest_field,
        )
        teams[team_id] = (request, soft_fields)

    return teams


def generate_user_pool() -> dict[int, tuple[str, UserIntentFields]]:
    rng = random.Random(_SEED + 1)  # 팀 생성과 다른 시드 스트림
    users: dict[int, tuple[str, UserIntentFields]] = {}

    for user_id in range(1, _NUM_USERS + 1):
        role = rng.choice(list(RoleCode))
        experience_level = rng.choice(list(ExperienceLevel))
        skills = rng.sample(_SKILL_POOL[role], k=min(2, len(_SKILL_POOL[role])))
        interests = rng.sample(_DOMAINS, k=2)
        activity_style = rng.choice(_ACTIVITY_STYLES)
        activity_goal = rng.choice(_ACTIVITY_GOALS)

        level_phrase = {
            ExperienceLevel.BEGINNER: "이제 막 시작한 완전 초보자입니다.",
            ExperienceLevel.INTERMEDIATE: "관련 경험이 어느 정도 있습니다.",
            ExperienceLevel.ADVANCED: "실무에서 다년간 활동한 경력자입니다.",
        }[experience_level]
        conversation_text = (
            f"저는 {role.value} 역할로 참여하고 싶습니다. {level_phrase} "
            f"{', '.join(interests)} 분야에 관심이 많고, {activity_style}으로 활동하며 "
            f"{activity_goal}을 하고 싶습니다."
        )

        fields = UserIntentFields(
            desired_roles=[role],
            skills=skills,
            interests=interests,
            activity_goal=activity_goal,
            activity_style=activity_style,
            experience_level=experience_level,
        )
        users[user_id] = (conversation_text, fields)

    return users
