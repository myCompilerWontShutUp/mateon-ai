# 역할/경험 수준 코드의 단일 소스. AI 서버·FE·BE가 모두 이 값을 그대로 쓴다(2026-11-05 결정 —
# BE/FE가 AI 서버의 도메인을 따르기로 했다). 역할을 추가하려면 _ROLES_BY_DOMAIN에 코드·한글
# 라벨만 넣으면 된다 — 이 값을 참조하는 프롬프트(app/features/user_to_team/extraction.py,
# app/features/team_embedding/extraction.py, app/features/user_to_team/chat_reply.py)가 자동으로
# 최신 목록을 LLM에 전달한다. BE/FE에 공유하는 docs/domain-enums.md는
# `scripts/generate_domain_doc.py`로 다시 생성한다(tests/test_domain_enums.py가 동기화 여부를 검사).
#
# 구조: 공모전 도메인(RoleDomain, 23개) → 도메인별 역할(RoleCode). IT에 BE/FE가 있듯 요리에는
# 한식·양식·중식·메뉴 기획이 있는 식이다. 도메인은 위비티·콘테스트코리아·올콘의 공모전 분야와
# 링커리어 관심분야(BE 공모전 데이터의 ContestField 21개)를 합쳐 잡았다(출처는 docs/domain-enums.md).
# 역할은 도메인별로 정리돼 있지만, 팀은 다른 도메인의 역할도 모집할 수 있다(예: 요리 공모전 팀이
# 영상 편집자를 모집하면 VIDEO_EDITING).
#
# 처음 10개 값(BE/FE/Design/PM/Data/MARKETING/CONTENT/BUSINESS/RESEARCH/ETC)은 문자열을 바꾸지
# 않는다 — BE에 이미 저장된 metadata, Supabase의 클러스터 키("BE:beginner" 등),
# tests/fixtures/*.json에 이 문자열이 그대로 있다. 이 10개는 각자 맞는 도메인에 들어갔고(BE/FE/
# Design/PM/Data → IT 등), 겹치는 의미를 새 코드로 떼어내 라벨(의미 범위)이 좁아진 것들이 있다(예:
# AI는 Data에서 IT_AI로). 그 전에 저장된 값은 BE가 팀 임베딩 재계산·의도 재추출로 다시 정규화하는
# 게 정확하다. 새 코드는 도메인 접두어를 붙인 대문자 스네이크로 짓는다(매칭은 overlap_ratio가
# 소문자로 비교하므로 대소문자는 스코어링에 영향 없음).
from enum import StrEnum

from app.schemas.contest import ContestField


class RoleDomain(StrEnum):
    """역할을 묶는 공모전 도메인. API 요청/응답의 역할 값은 항상 RoleCode이고, 도메인은 FE의 역할
    선택 화면과 LLM 프롬프트의 코드 목록을 도메인별로 보여주는 데 쓴다."""

    IT = "IT"
    GAME = "GAME"
    PLANNING_IDEA = "PLANNING_IDEA"
    MARKETING_AD = "MARKETING_AD"
    DESIGN_CHARACTER_WEBTOON = "DESIGN_CHARACTER_WEBTOON"
    VIDEO_PHOTO = "VIDEO_PHOTO"
    MEDIA_CONTENT = "MEDIA_CONTENT"
    LITERATURE = "LITERATURE"
    ACADEMIC = "ACADEMIC"
    SCIENCE_ENGINEERING = "SCIENCE_ENGINEERING"
    ARCHITECTURE = "ARCHITECTURE"
    POLICY_SOCIETY = "POLICY_SOCIETY"
    BUSINESS_ECONOMY = "BUSINESS_ECONOMY"
    ARTS_PERFORMANCE = "ARTS_PERFORMANCE"
    COOKING_FOOD = "COOKING_FOOD"
    FASHION_BEAUTY = "FASHION_BEAUTY"
    SPORTS = "SPORTS"
    EDUCATION = "EDUCATION"
    SOCIAL_VOLUNTEER = "SOCIAL_VOLUNTEER"
    EVENT_FESTIVAL = "EVENT_FESTIVAL"
    HEALTH_MEDICAL = "HEALTH_MEDICAL"
    TRAVEL_CULTURE = "TRAVEL_CULTURE"
    OTHER = "OTHER"


ROLE_DOMAIN_LABELS: dict[RoleDomain, str] = {
    RoleDomain.IT: "IT·소프트웨어",
    RoleDomain.GAME: "게임·XR",
    RoleDomain.PLANNING_IDEA: "기획·아이디어",
    RoleDomain.MARKETING_AD: "광고·마케팅·네이밍",
    RoleDomain.DESIGN_CHARACTER_WEBTOON: "디자인·캐릭터·웹툰",
    RoleDomain.VIDEO_PHOTO: "사진·영상",
    RoleDomain.MEDIA_CONTENT: "언론·미디어·콘텐츠",
    RoleDomain.LITERATURE: "문학·글쓰기",
    RoleDomain.ACADEMIC: "논문·학술",
    RoleDomain.SCIENCE_ENGINEERING: "과학·공학",
    RoleDomain.ARCHITECTURE: "건축·건설·인테리어",
    RoleDomain.POLICY_SOCIETY: "정치·사회·법률",
    RoleDomain.BUSINESS_ECONOMY: "경영·경제·창업",
    RoleDomain.ARTS_PERFORMANCE: "음악·공연·예술",
    RoleDomain.COOKING_FOOD: "요리·식품",
    RoleDomain.FASHION_BEAUTY: "패션·뷰티",
    RoleDomain.SPORTS: "스포츠",
    RoleDomain.EDUCATION: "교육·멘토링",
    RoleDomain.SOCIAL_VOLUNTEER: "봉사·사회공헌·교류",
    RoleDomain.EVENT_FESTIVAL: "행사·축제·전시",
    RoleDomain.HEALTH_MEDICAL: "의료·보건",
    RoleDomain.TRAVEL_CULTURE: "여행·관광·문화",
    RoleDomain.OTHER: "기타",
}


class RoleCode(StrEnum):
    # IT·소프트웨어
    BE = "BE"
    FE = "FE"
    IT_MOBILE = "IT_MOBILE"
    IT_AI = "IT_AI"
    DATA = "Data"
    IT_DATA_VIZ = "IT_DATA_VIZ"
    IT_SECURITY = "IT_SECURITY"
    IT_EMBEDDED = "IT_EMBEDDED"
    DESIGN = "Design"
    PM = "PM"
    # 게임·XR
    GAME_PROGRAMMING = "GAME_PROGRAMMING"
    GAME_PLANNING = "GAME_PLANNING"
    GAME_ART = "GAME_ART"
    GAME_SOUND = "GAME_SOUND"
    GAME_ESPORTS = "GAME_ESPORTS"
    # 기획·아이디어 (다른 도메인 팀도 흔히 모집하는 공통 역할이기도 하다)
    IDEA_PLANNING = "IDEA_PLANNING"
    RESEARCH = "RESEARCH"
    IDEA_PITCHING = "IDEA_PITCHING"
    # 광고·마케팅·네이밍
    MARKETING = "MARKETING"
    AD_PLANNING = "AD_PLANNING"
    AD_COPYWRITING = "AD_COPYWRITING"
    AD_SNS = "AD_SNS"
    AD_PERFORMANCE = "AD_PERFORMANCE"
    # 디자인·캐릭터·웹툰
    DESIGN_GRAPHIC = "DESIGN_GRAPHIC"
    DESIGN_PPT = "DESIGN_PPT"
    DESIGN_PRODUCT = "DESIGN_PRODUCT"
    DESIGN_CHARACTER = "DESIGN_CHARACTER"
    DESIGN_WEBTOON = "DESIGN_WEBTOON"
    DESIGN_ILLUSTRATION = "DESIGN_ILLUSTRATION"
    DESIGN_MOTION = "DESIGN_MOTION"
    # 사진·영상
    VIDEO_DIRECTING = "VIDEO_DIRECTING"
    VIDEO_FILMING = "VIDEO_FILMING"
    VIDEO_EDITING = "VIDEO_EDITING"
    VIDEO_SCRIPT = "VIDEO_SCRIPT"
    VIDEO_GENAI = "VIDEO_GENAI"
    PHOTO = "PHOTO"
    # 언론·미디어·콘텐츠
    CONTENT = "CONTENT"
    MEDIA_JOURNALIST = "MEDIA_JOURNALIST"
    MEDIA_ANNOUNCER = "MEDIA_ANNOUNCER"
    MEDIA_CREATOR = "MEDIA_CREATOR"
    MEDIA_BROADCAST = "MEDIA_BROADCAST"
    # 문학·글쓰기
    LIT_POETRY = "LIT_POETRY"
    LIT_NOVEL = "LIT_NOVEL"
    LIT_ESSAY = "LIT_ESSAY"
    LIT_SCENARIO = "LIT_SCENARIO"
    LIT_CHILDREN = "LIT_CHILDREN"
    LIT_REVIEW = "LIT_REVIEW"
    LIT_STORY = "LIT_STORY"
    LIT_EDITING = "LIT_EDITING"
    # 논문·학술
    ACAD_PAPER = "ACAD_PAPER"
    ACAD_STATISTICS = "ACAD_STATISTICS"
    ACAD_SURVEY = "ACAD_SURVEY"
    ACAD_LIT_REVIEW = "ACAD_LIT_REVIEW"
    # 과학·공학
    SCI_RESEARCH = "SCI_RESEARCH"
    SCI_BIO = "SCI_BIO"
    ENG_MECHANICAL = "ENG_MECHANICAL"
    ENG_ELECTRICAL = "ENG_ELECTRICAL"
    ENG_CHEMICAL = "ENG_CHEMICAL"
    ENG_ENVIRONMENT = "ENG_ENVIRONMENT"
    ENG_ROBOTICS = "ENG_ROBOTICS"
    SCI_PATENT = "SCI_PATENT"
    # 건축·건설·인테리어
    ARCH_DESIGN = "ARCH_DESIGN"
    ARCH_INTERIOR = "ARCH_INTERIOR"
    ARCH_LANDSCAPE = "ARCH_LANDSCAPE"
    ARCH_URBAN = "ARCH_URBAN"
    ARCH_STRUCTURE = "ARCH_STRUCTURE"
    ARCH_CONSTRUCTION = "ARCH_CONSTRUCTION"
    ARCH_MODELING = "ARCH_MODELING"
    ARCH_PANEL = "ARCH_PANEL"
    # 정치·사회·법률
    POLICY_PROPOSAL = "POLICY_PROPOSAL"
    POLICY_LAW = "POLICY_LAW"
    POLICY_DEBATE = "POLICY_DEBATE"
    POLICY_CAMPAIGN = "POLICY_CAMPAIGN"
    # 경영·경제·창업
    BUSINESS = "BUSINESS"
    BIZ_FINANCE = "BIZ_FINANCE"
    BIZ_ECONOMICS = "BIZ_ECONOMICS"
    BIZ_TRADE = "BIZ_TRADE"
    BIZ_CONSULTING = "BIZ_CONSULTING"
    BIZ_LOGISTICS = "BIZ_LOGISTICS"
    BIZ_SALES = "BIZ_SALES"
    # 음악·공연·예술
    ARTS_VOCAL = "ARTS_VOCAL"
    ARTS_INSTRUMENT = "ARTS_INSTRUMENT"
    ARTS_COMPOSING = "ARTS_COMPOSING"
    ARTS_SOUND = "ARTS_SOUND"
    ARTS_DANCE = "ARTS_DANCE"
    ARTS_ACTING = "ARTS_ACTING"
    ARTS_FINE_ART = "ARTS_FINE_ART"
    ARTS_STAGE = "ARTS_STAGE"
    ARTS_LIGHTING = "ARTS_LIGHTING"
    ARTS_STAGE_ART = "ARTS_STAGE_ART"
    # 요리·식품
    COOK_KOREAN = "COOK_KOREAN"
    COOK_WESTERN = "COOK_WESTERN"
    COOK_CHINESE = "COOK_CHINESE"
    COOK_JAPANESE = "COOK_JAPANESE"
    COOK_BAKERY = "COOK_BAKERY"
    COOK_RICE_CAKE = "COOK_RICE_CAKE"
    COOK_BEVERAGE = "COOK_BEVERAGE"
    COOK_STYLING = "COOK_STYLING"
    COOK_MENU_PLANNING = "COOK_MENU_PLANNING"
    COOK_FOOD_PRODUCT = "COOK_FOOD_PRODUCT"
    # 패션·뷰티
    FASHION_DESIGN = "FASHION_DESIGN"
    FASHION_PATTERN = "FASHION_PATTERN"
    FASHION_STYLING = "FASHION_STYLING"
    FASHION_MODEL = "FASHION_MODEL"
    FASHION_MD = "FASHION_MD"
    BEAUTY_MAKEUP = "BEAUTY_MAKEUP"
    BEAUTY_HAIR = "BEAUTY_HAIR"
    BEAUTY_NAIL_SKIN = "BEAUTY_NAIL_SKIN"
    BEAUTY_PRODUCT = "BEAUTY_PRODUCT"
    # 스포츠
    SPORTS_PLAYER = "SPORTS_PLAYER"
    SPORTS_COACH = "SPORTS_COACH"
    SPORTS_ANALYTICS = "SPORTS_ANALYTICS"
    SPORTS_MANAGER = "SPORTS_MANAGER"
    # 교육·멘토링
    EDU_CURRICULUM = "EDU_CURRICULUM"
    EDU_TEACHING = "EDU_TEACHING"
    EDU_MENTORING = "EDU_MENTORING"
    EDU_CONTENT = "EDU_CONTENT"
    # 봉사·사회공헌·교류
    VOLUNTEER_FIELD = "VOLUNTEER_FIELD"
    VOLUNTEER_PLANNING = "VOLUNTEER_PLANNING"
    GLOBAL_EXCHANGE = "GLOBAL_EXCHANGE"
    GLOBAL_TRANSLATION = "GLOBAL_TRANSLATION"
    # 행사·축제·전시
    EVENT_PLANNING = "EVENT_PLANNING"
    EVENT_OPERATION = "EVENT_OPERATION"
    EVENT_EXHIBITION = "EVENT_EXHIBITION"
    EVENT_OUTREACH = "EVENT_OUTREACH"
    # 의료·보건
    HEALTH_CLINICAL = "HEALTH_CLINICAL"
    HEALTH_PUBLIC = "HEALTH_PUBLIC"
    HEALTH_MENTAL = "HEALTH_MENTAL"
    # 여행·관광·문화
    TRAVEL_PLANNING = "TRAVEL_PLANNING"
    TRAVEL_HERITAGE = "TRAVEL_HERITAGE"
    TRAVEL_GUIDE = "TRAVEL_GUIDE"
    # 기타
    ETC = "ETC"


# 도메인 → {역할: 한글 라벨}. 라벨은 화면 표시와 LLM 분류 기준을 겸한다 — 추천 라벨처럼 도메인
# 없이 따로 보일 때도 뜻이 통하게("양식"이 아니라 "양식 요리") 적고, 같은 일을 두 코드가 나눠
# 갖지 않게 범위를 나눈다(겹치면 사용자·팀이 다른 코드로 정규화돼 역할 일치도가 0이 된다).
_ROLES_BY_DOMAIN: dict[RoleDomain, dict[RoleCode, str]] = {
    RoleDomain.IT: {
        RoleCode.BE: "백엔드 개발",
        RoleCode.FE: "웹 프론트엔드 개발",
        RoleCode.IT_MOBILE: "모바일 앱 개발",
        RoleCode.IT_AI: "AI/머신러닝 개발",
        RoleCode.DATA: "데이터 분석/엔지니어링",
        RoleCode.IT_DATA_VIZ: "데이터 시각화/대시보드",
        RoleCode.IT_SECURITY: "정보보안",
        RoleCode.IT_EMBEDDED: "임베디드/펌웨어/IoT 개발",
        RoleCode.DESIGN: "UI/UX 디자인",
        RoleCode.PM: "서비스 기획/PM",
    },
    RoleDomain.GAME: {
        RoleCode.GAME_PROGRAMMING: "게임/XR 프로그래밍",
        RoleCode.GAME_PLANNING: "게임 기획/시나리오",
        RoleCode.GAME_ART: "게임/XR 그래픽",
        RoleCode.GAME_SOUND: "게임 음악/효과음",
        RoleCode.GAME_ESPORTS: "e스포츠 선수",
    },
    RoleDomain.PLANNING_IDEA: {
        RoleCode.IDEA_PLANNING: "아이디어 기획/기획서 작성",
        RoleCode.RESEARCH: "자료조사/리서치",
        RoleCode.IDEA_PITCHING: "발표/피칭/스피치",
    },
    RoleDomain.MARKETING_AD: {
        RoleCode.MARKETING: "마케팅 기획/전략",
        RoleCode.AD_PLANNING: "광고/PR 기획",
        RoleCode.AD_COPYWRITING: "카피라이팅/네이밍/슬로건",
        RoleCode.AD_SNS: "SNS 마케팅/홍보",
        RoleCode.AD_PERFORMANCE: "퍼포먼스 마케팅",
    },
    RoleDomain.DESIGN_CHARACTER_WEBTOON: {
        RoleCode.DESIGN_GRAPHIC: "그래픽/포스터/카드뉴스 디자인",
        RoleCode.DESIGN_PPT: "PPT 디자인",
        RoleCode.DESIGN_PRODUCT: "제품/상품 디자인",
        RoleCode.DESIGN_CHARACTER: "캐릭터 디자인",
        RoleCode.DESIGN_WEBTOON: "웹툰/만화 작화",
        RoleCode.DESIGN_ILLUSTRATION: "일러스트레이션",
        RoleCode.DESIGN_MOTION: "모션그래픽/애니메이션/미디어아트",
    },
    RoleDomain.VIDEO_PHOTO: {
        RoleCode.VIDEO_DIRECTING: "영상 연출",
        RoleCode.VIDEO_FILMING: "영상 촬영/조명",
        RoleCode.VIDEO_EDITING: "영상 편집",
        RoleCode.VIDEO_SCRIPT: "영상 대본/구성",
        RoleCode.VIDEO_GENAI: "생성형 AI 영상/이미지 제작",
        RoleCode.PHOTO: "사진 촬영/보정",
    },
    RoleDomain.MEDIA_CONTENT: {
        RoleCode.CONTENT: "블로그/텍스트 콘텐츠 에디터",
        RoleCode.MEDIA_JOURNALIST: "취재기자/기사 작성",
        RoleCode.MEDIA_ANNOUNCER: "아나운서/MC/리포터",
        RoleCode.MEDIA_CREATOR: "숏폼/유튜브 크리에이터",
        RoleCode.MEDIA_BROADCAST: "방송/라디오 PD",
    },
    RoleDomain.LITERATURE: {
        RoleCode.LIT_POETRY: "시 창작",
        RoleCode.LIT_NOVEL: "소설/웹소설 창작",
        RoleCode.LIT_ESSAY: "수필/에세이/수기",
        RoleCode.LIT_SCENARIO: "시나리오/극본/희곡",
        RoleCode.LIT_CHILDREN: "동화/그림책 글 창작",
        RoleCode.LIT_REVIEW: "독후감/서평/비평",
        RoleCode.LIT_STORY: "스토리 작가/웹툰 글작가",
        RoleCode.LIT_EDITING: "출판 편집/교정",
    },
    RoleDomain.ACADEMIC: {
        RoleCode.ACAD_PAPER: "논문/학술 리포트 작성",
        RoleCode.ACAD_STATISTICS: "통계/계량 분석",
        RoleCode.ACAD_SURVEY: "설문/인터뷰 조사",
        RoleCode.ACAD_LIT_REVIEW: "선행연구/문헌 검토",
    },
    RoleDomain.SCIENCE_ENGINEERING: {
        RoleCode.SCI_RESEARCH: "자연과학 실험/연구",
        RoleCode.SCI_BIO: "생명과학/바이오",
        RoleCode.ENG_MECHANICAL: "기계 설계/3D CAD",
        RoleCode.ENG_ELECTRICAL: "전기/전자회로 설계",
        RoleCode.ENG_CHEMICAL: "화학/소재 공학",
        RoleCode.ENG_ENVIRONMENT: "환경/에너지 공학",
        RoleCode.ENG_ROBOTICS: "로봇/드론/자율주행 소프트웨어",
        RoleCode.SCI_PATENT: "특허 분석/전략",
    },
    RoleDomain.ARCHITECTURE: {
        RoleCode.ARCH_DESIGN: "건축 설계",
        RoleCode.ARCH_INTERIOR: "인테리어/공간 디자인",
        RoleCode.ARCH_LANDSCAPE: "조경 설계",
        RoleCode.ARCH_URBAN: "도시계획/도시설계",
        RoleCode.ARCH_STRUCTURE: "구조/토목 설계",
        RoleCode.ARCH_CONSTRUCTION: "시공/건설사업관리",
        RoleCode.ARCH_MODELING: "건축 3D 모델링/BIM/렌더링",
        RoleCode.ARCH_PANEL: "건축 패널/모형 제작",
    },
    RoleDomain.POLICY_SOCIETY: {
        RoleCode.POLICY_PROPOSAL: "정책 제안/기획",
        RoleCode.POLICY_LAW: "모의재판/법률 검토",
        RoleCode.POLICY_DEBATE: "토론/디베이트",
        RoleCode.POLICY_CAMPAIGN: "사회·환경 캠페인 기획",
    },
    RoleDomain.BUSINESS_ECONOMY: {
        RoleCode.BUSINESS: "사업 기획/사업계획서 작성",
        RoleCode.BIZ_FINANCE: "재무/회계/투자 분석",
        RoleCode.BIZ_ECONOMICS: "경제 분석",
        RoleCode.BIZ_TRADE: "무역/국제통상",
        RoleCode.BIZ_CONSULTING: "경영 컨설팅/케이스 분석",
        RoleCode.BIZ_LOGISTICS: "유통/물류/SCM",
        RoleCode.BIZ_SALES: "영업/제휴",
    },
    RoleDomain.ARTS_PERFORMANCE: {
        RoleCode.ARTS_VOCAL: "보컬/랩",
        RoleCode.ARTS_INSTRUMENT: "악기 연주/세션",
        RoleCode.ARTS_COMPOSING: "작사/작곡/편곡",
        RoleCode.ARTS_SOUND: "음향/녹음/믹싱",
        RoleCode.ARTS_DANCE: "댄스/안무/치어리딩",
        RoleCode.ARTS_ACTING: "연기/배우/성우",
        RoleCode.ARTS_FINE_ART: "회화/벽화/순수미술",
        RoleCode.ARTS_STAGE: "공연 기획/연출",
        RoleCode.ARTS_LIGHTING: "무대 조명",
        RoleCode.ARTS_STAGE_ART: "무대 미술/의상/소품",
    },
    RoleDomain.COOKING_FOOD: {
        RoleCode.COOK_KOREAN: "한식 요리",
        RoleCode.COOK_WESTERN: "양식 요리",
        RoleCode.COOK_CHINESE: "중식 요리",
        RoleCode.COOK_JAPANESE: "일식 요리",
        RoleCode.COOK_BAKERY: "제과/제빵/디저트",
        RoleCode.COOK_RICE_CAKE: "떡/한과",
        RoleCode.COOK_BEVERAGE: "음료/바리스타/칵테일",
        RoleCode.COOK_STYLING: "푸드스타일링/테이블 세팅",
        RoleCode.COOK_MENU_PLANNING: "레시피/메뉴 개발/외식 기획",
        RoleCode.COOK_FOOD_PRODUCT: "가공식품 개발/식품공학",
    },
    RoleDomain.FASHION_BEAUTY: {
        RoleCode.FASHION_DESIGN: "패션 디자인",
        RoleCode.FASHION_PATTERN: "패턴메이킹/봉제",
        RoleCode.FASHION_STYLING: "패션 스타일링",
        RoleCode.FASHION_MODEL: "패션 모델",
        RoleCode.FASHION_MD: "패션 기획/MD",
        RoleCode.BEAUTY_MAKEUP: "메이크업/분장",
        RoleCode.BEAUTY_HAIR: "헤어 디자인",
        RoleCode.BEAUTY_NAIL_SKIN: "네일/피부 미용",
        RoleCode.BEAUTY_PRODUCT: "뷰티 제품 기획",
    },
    RoleDomain.SPORTS: {
        RoleCode.SPORTS_PLAYER: "운동선수",
        RoleCode.SPORTS_COACH: "코치/트레이너",
        RoleCode.SPORTS_ANALYTICS: "경기 분석",
        RoleCode.SPORTS_MANAGER: "스포츠 팀 매니저",
    },
    RoleDomain.EDUCATION: {
        RoleCode.EDU_CURRICULUM: "교육 프로그램/교안 개발",
        RoleCode.EDU_TEACHING: "강의/학습 지도",
        RoleCode.EDU_MENTORING: "진로/전공 멘토링",
        RoleCode.EDU_CONTENT: "교육 자료/교구 제작",
    },
    RoleDomain.SOCIAL_VOLUNTEER: {
        RoleCode.VOLUNTEER_FIELD: "현장 봉사",
        RoleCode.VOLUNTEER_PLANNING: "봉사·사회공헌 프로그램 기획",
        RoleCode.GLOBAL_EXCHANGE: "국제 교류/해외 탐방",
        RoleCode.GLOBAL_TRANSLATION: "통번역/외국어",
    },
    RoleDomain.EVENT_FESTIVAL: {
        RoleCode.EVENT_PLANNING: "행사/축제 기획",
        RoleCode.EVENT_OPERATION: "행사 현장 운영/스태프",
        RoleCode.EVENT_EXHIBITION: "전시/박람회/부스 기획",
        RoleCode.EVENT_OUTREACH: "섭외/협찬/후원 유치",
    },
    RoleDomain.HEALTH_MEDICAL: {
        RoleCode.HEALTH_CLINICAL: "의료계열 전문 지식/자문",
        RoleCode.HEALTH_PUBLIC: "보건 정책/건강증진 캠페인",
        RoleCode.HEALTH_MENTAL: "심리학/정신건강",
    },
    RoleDomain.TRAVEL_CULTURE: {
        RoleCode.TRAVEL_PLANNING: "관광 상품/코스 기획",
        RoleCode.TRAVEL_HERITAGE: "문화유산/역사 콘텐츠",
        RoleCode.TRAVEL_GUIDE: "관광·전시 해설/가이드",
    },
    RoleDomain.OTHER: {
        RoleCode.ETC: "기타",
    },
}

ROLE_CODE_LABELS: dict[RoleCode, str] = {
    code: label for roles in _ROLES_BY_DOMAIN.values() for code, label in roles.items()
}
ROLE_DOMAINS: dict[RoleCode, RoleDomain] = {
    code: domain for domain, roles in _ROLES_BY_DOMAIN.items() for code in roles
}

# 값을 바꾸면 안 되는 처음 10개 코드(맨 위 주석 참고) — tests/test_domain_enums.py가 검사한다.
FROZEN_ROLE_CODE_VALUES: tuple[str, ...] = (
    "BE", "FE", "Design", "PM", "Data", "MARKETING", "CONTENT", "BUSINESS", "RESEARCH", "ETC",
)

# BE 공모전 데이터의 분야(ContestField, 링커리어 관심분야 기준) → 그 공모전 팀이 주로 모집할 역할
# 도메인(앞에 올수록 많이 모집한다). FE가 공모전에 딸린 팀의 역할 선택 화면에서 어느 도메인을 먼저
# 보여줄지 정하는 용도다(제한이 아니다 — 팀은 어느 도메인의 역할이든 모집할 수 있다). BE가 수집한
# 공모전 414건(data/result_events.json)의 분야별 실제 공고로 순서를 정했고, ContestField에 따로 없는
# 건축·문학·논문·게임도 그 공고들이 실린 분야에 이어 두었다(2026-11-05 — 모든 도메인이 최소 한
# 분야에서 보인다).
CONTEST_FIELD_DOMAINS: dict[ContestField, tuple[RoleDomain, ...]] = {
    ContestField.TRAVEL_HOTEL_AIRLINE: (RoleDomain.TRAVEL_CULTURE, RoleDomain.MEDIA_CONTENT),
    ContestField.PRESS_MEDIA: (RoleDomain.MEDIA_CONTENT, RoleDomain.VIDEO_PHOTO),
    ContestField.CULTURE_HISTORY: (
        RoleDomain.TRAVEL_CULTURE,
        RoleDomain.LITERATURE,
        RoleDomain.ARTS_PERFORMANCE,
    ),
    ContestField.EVENT_FESTIVAL: (
        RoleDomain.EVENT_FESTIVAL,
        RoleDomain.ARTS_PERFORMANCE,
        RoleDomain.MARKETING_AD,
    ),
    ContestField.EDUCATION: (RoleDomain.EDUCATION,),
    ContestField.DESIGN_PHOTO_ART_VIDEO: (
        RoleDomain.DESIGN_CHARACTER_WEBTOON,
        RoleDomain.VIDEO_PHOTO,
        RoleDomain.ARTS_PERFORMANCE,
        RoleDomain.FASHION_BEAUTY,
    ),
    ContestField.ECONOMY_FINANCE: (
        RoleDomain.BUSINESS_ECONOMY,
        RoleDomain.PLANNING_IDEA,
        RoleDomain.ACADEMIC,
    ),
    ContestField.MANAGEMENT_CONSULTING_MARKETING: (
        RoleDomain.MARKETING_AD,
        RoleDomain.MEDIA_CONTENT,
        RoleDomain.BUSINESS_ECONOMY,
    ),
    ContestField.POLITICS_SOCIETY_LAW: (RoleDomain.POLICY_SOCIETY, RoleDomain.ACADEMIC),
    ContestField.SPORTS_FITNESS: (RoleDomain.SPORTS, RoleDomain.MARKETING_AD),
    ContestField.MEDICAL_HEALTH: (RoleDomain.HEALTH_MEDICAL, RoleDomain.IT),
    ContestField.BEAUTY_COSMETICS: (
        RoleDomain.FASHION_BEAUTY,
        RoleDomain.MEDIA_CONTENT,
        RoleDomain.VIDEO_PHOTO,
    ),
    ContestField.SCIENCE_ENGINEERING_TECH_IT: (
        RoleDomain.IT,
        RoleDomain.SCIENCE_ENGINEERING,
        RoleDomain.GAME,
        RoleDomain.ARCHITECTURE,
    ),
    ContestField.COOKING_FOOD: (
        RoleDomain.COOKING_FOOD,
        RoleDomain.MARKETING_AD,
        RoleDomain.VIDEO_PHOTO,
    ),
    ContestField.STARTUP_SELF_DEVELOPMENT: (
        RoleDomain.BUSINESS_ECONOMY,
        RoleDomain.IT,
        RoleDomain.PLANNING_IDEA,
    ),
    ContestField.ENVIRONMENT_ENERGY: (
        RoleDomain.POLICY_SOCIETY,
        RoleDomain.SCIENCE_ENGINEERING,
        RoleDomain.PLANNING_IDEA,
    ),
    ContestField.CONTENTS: (
        RoleDomain.MEDIA_CONTENT,
        RoleDomain.VIDEO_PHOTO,
        RoleDomain.LITERATURE,
        RoleDomain.GAME,
    ),
    ContestField.SOCIAL_CONTRIBUTION_EXCHANGE: (RoleDomain.SOCIAL_VOLUNTEER, RoleDomain.EDUCATION),
    ContestField.DISTRIBUTION_LOGISTICS: (RoleDomain.BUSINESS_ECONOMY,),
    ContestField.PLANNING_IDEA: (
        RoleDomain.PLANNING_IDEA,
        RoleDomain.DESIGN_CHARACTER_WEBTOON,
        RoleDomain.MARKETING_AD,
    ),
    ContestField.ETC: (RoleDomain.OTHER,),
}


class ExperienceLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


EXPERIENCE_LEVEL_LABELS: dict[ExperienceLevel, str] = {
    ExperienceLevel.BEGINNER: "초보",
    ExperienceLevel.INTERMEDIATE: "중급",
    ExperienceLevel.ADVANCED: "숙련",
}


def role_code_prompt_listing() -> str:
    """LLM 프롬프트에 그대로 붙여 넣을 도메인별 코드 목록 — 한 줄에 '[도메인] CODE(라벨), ...'.

    도메인으로 묶어 보여주는 이유: 코드가 100개를 넘으면 평면 나열로는 "기획"처럼 여러 도메인에
    있는 일을 LLM이 아무 코드로나 고르기 쉽다. 먼저 도메인을 정하고 그 안에서 고르게 한다.
    """
    return "\n".join(
        f"[{ROLE_DOMAIN_LABELS[domain]}] "
        + ", ".join(f"{code.value}({label})" for code, label in roles.items())
        for domain, roles in _ROLES_BY_DOMAIN.items()
    )


def role_code_translation_guide() -> str:
    """자연어 응답 생성용 — 'CODE→라벨' 번역 가이드 문자열."""
    return ", ".join(f"{code.value}→{label}" for code, label in ROLE_CODE_LABELS.items())


def role_label(code: str) -> str:
    """역할 코드의 한글 라벨. 코드가 아닌 값(이 enum 도입 전에 저장된 자유 텍스트 등)은 그대로
    돌려준다 — 화면에 코드 값이 그대로 노출되지 않게 하면서도 옛 값 때문에 에러가 나지 않게."""
    try:
        return ROLE_CODE_LABELS[RoleCode(code)]
    except ValueError:
        return code
