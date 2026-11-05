"""BE·FE 공유용 도메인 코드 표(docs/domain-enums.md)를 코드에서 만든다.

문서를 손으로 고치면 코드와 어긋나기 쉬워서, 표는 항상 enum과 라벨 dict에서 생성한다.
`scripts/generate_domain_doc.py`가 이 함수로 파일을 쓰고, tests/test_domain_enums.py가 파일이
최신인지 검사한다.
"""

from pathlib import Path

from app.schemas.activity import ACTIVITY_STYLE_LABELS
from app.schemas.contest import CONTEST_CATEGORY_LABELS, CONTEST_FIELD_LABELS
from app.schemas.role_codes import (
    CONTEST_FIELD_DOMAINS,
    EXPERIENCE_LEVEL_LABELS,
    FROZEN_ROLE_CODE_VALUES,
    ROLE_CODE_LABELS,
    ROLE_DOMAIN_LABELS,
    ROLE_DOMAINS,
    RoleDomain,
)

DOC_PATH = Path(__file__).resolve().parents[2] / "docs" / "domain-enums.md"

# 도메인을 잡을 때 근거로 삼은 각 사이트의 분야 이름(2026-11-05 확인, 사이트 표기 그대로). 링커리어는
# 분야 목록이 자바스크립트로 그려져 직접 읽지 못해, BE가 링커리어에서 수집한 공모전 데이터의
# 분야(ContestField)로 대신했다.
_DOMAIN_SOURCES: dict[RoleDomain, str] = {
    RoleDomain.IT: "위비티 웹/모바일/IT · 콘테스트코리아 학문•과학•IT · 올콘 개발 · 링커리어 과학/공학/기술/IT",
    RoleDomain.GAME: "위비티 게임/소프트웨어 · 올콘 e스포츠",
    RoleDomain.PLANNING_IDEA: "위비티 기획/아이디어 · 콘테스트코리아 아이디어•건축•창업 · 올콘 기획, 아이디어 · 링커리어 기획/아이디어",
    RoleDomain.MARKETING_AD: "위비티 광고/마케팅, 네이밍/슬로건 · 콘테스트코리아 네이밍•슬로건, 기획•홍보•마케팅 · 올콘 마케팅, 네이밍, 슬로건, 광고",
    RoleDomain.DESIGN_CHARACTER_WEBTOON: "위비티 디자인/캐릭터/웹툰 · 콘테스트코리아 미술•디자인•웹툰 · 올콘 디자인·그림·웹툰",
    RoleDomain.VIDEO_PHOTO: "위비티 영상/UCC/사진 · 콘테스트코리아 사진•영상•영화제 · 올콘 사진·영상",
    RoleDomain.MEDIA_CONTENT: "콘테스트코리아 서포터즈•기자단 · 올콘 서포터즈/기자단 · 링커리어 언론/미디어, 콘텐츠",
    RoleDomain.LITERATURE: "위비티 문학/글/시나리오 · 콘테스트코리아 문학•문예 · 올콘 시, 소설, 수기, 시나리오",
    RoleDomain.ACADEMIC: "위비티 논문/리포트 · 콘테스트코리아 학문•과학•IT · 올콘 논문",
    RoleDomain.SCIENCE_ENGINEERING: "위비티 과학/공학 · 콘테스트코리아 학문•과학•IT · 올콘 과학·공학·학술 · 링커리어 환경/에너지",
    RoleDomain.ARCHITECTURE: "위비티 건축/건설/인테리어 · 콘테스트코리아 아이디어•건축•창업 · 올콘 도시건축, 건축, 건설, 인테리어",
    RoleDomain.POLICY_SOCIETY: "올콘 정책제안 · 링커리어 정치/사회/법률",
    RoleDomain.BUSINESS_ECONOMY: "위비티 취업/창업 · 올콘 창업 · 링커리어 경영/컨설팅/마케팅, 경제/금융, 창업/자기계발, 유통/물류",
    RoleDomain.ARTS_PERFORMANCE: "위비티 예체능/미술/음악 · 콘테스트코리아 음악•콩쿠르•댄스, 요리•뷰티•배우•오디션 · 올콘 음악, 콩쿠르, 댄스, 연기",
    RoleDomain.COOKING_FOOD: "콘테스트코리아 요리•뷰티•배우•오디션 · 올콘 요리 · 링커리어 요리/식품 · 세부 역할은 대한민국 국제요리&제과 경연대회 종목 참고",
    RoleDomain.FASHION_BEAUTY: "콘테스트코리아 요리•뷰티•배우•오디션 · 올콘 패션, 뷰티 · 링커리어 뷰티/미용/화장품",
    RoleDomain.SPORTS: "콘테스트코리아 스포츠 · 올콘 스포츠 · 링커리어 체육/헬스",
    RoleDomain.EDUCATION: "콘테스트코리아 교육•강연•멘토링•세미나 · 링커리어 교육",
    RoleDomain.SOCIAL_VOLUNTEER: "위비티 봉사활동, 해외 · 콘테스트코리아 인턴•체험•탐방•봉사•동아리 · 올콘 국내봉사/해외봉사 · 링커리어 사회공헌/교류",
    RoleDomain.EVENT_FESTIVAL: "콘테스트코리아 전시•박람•행사•축제 · 링커리어 행사/페스티벌",
    RoleDomain.HEALTH_MEDICAL: "링커리어 의료/보건",
    RoleDomain.TRAVEL_CULTURE: "링커리어 여행/호텔/항공, 문화/역사",
    RoleDomain.OTHER: "위비티·올콘 기타 · 콘테스트코리아 The 다양한 분야",
}

# 도메인별 역할 구성의 근거(2026-11-05 조사). 링커리어 팀원 모집 글, 대회 모집 요강, 대학 연합동아리
# 파트 구성처럼 실제로 팀이 어떤 역할로 나뉘는지 보여주는 자료로 확인했다.
_ROLE_EVIDENCE: dict[RoleDomain, str] = {
    RoleDomain.IT: (
        "해커톤·IT 공모전 팀원 모집 글(기획·디자인·프론트엔드·백엔드·AI·데이터 수집/가공·"
        "데이터 시각화)과 IT 연합동아리 파트(UMC·YAPP: Web·Server·iOS·Android·Plan·Design)로 확인. "
        "인프라/DevOps를 따로 모집한 사례는 없음."
    ),
    RoleDomain.GAME: (
        "게임 공모전 신청서 세부 분야(프로그래밍/그래픽/기획/운영QA), 스마일게이트 멤버십(프로그래머/그래픽 디자이너/기획자), "
        "XR 서비스 경진대회 팀의 Unity 개발자 모집, e스포츠 대학리그(LoL 5인·PUBG 4인)로 확인."
    ),
    RoleDomain.PLANNING_IDEA: (
        "아이디어 공모전 팀은 기획(제안서 작성)·자료조사·발표로 나뉨(링커리어 팀원 모집 글). PPT 디자인 담당은 디자인 "
        "도메인으로 옮김."
    ),
    RoleDomain.MARKETING_AD: (
        "광고 공모전 팀(기획·카피·디자인·영상), PR 기획서 공모전, 퍼포먼스 마케팅 공모전, SNS 홍보 서포터즈(BE 데이터 "
        "경영/컨설팅/마케팅 154건 중 약 100건)로 확인."
    ),
    RoleDomain.DESIGN_CHARACTER_WEBTOON: (
        "광고 공모전 디자이너(포스터·스토리보드)·기자단 카드뉴스 담당·PPT 디자인 담당 모집, 웹툰 공모전의 작화 부문, "
        "애니메이션·모션그래픽 공모전으로 확인."
    ),
    RoleDomain.VIDEO_PHOTO: (
        "다큐·단편영화·영상 콘텐츠 팀의 연출·촬영·편집·대본 분담, 대학 방송국 구성, 생성형 AI 영상 공모전(BE 데이터 10건 "
        "안팎)으로 확인."
    ),
    RoleDomain.MEDIA_CONTENT: (
        "기자단(취재·동영상·카드뉴스·블로그 기자), 학생 리포터(에디터 팀·크리에이터 팀), 대학 방송국(PD·작가·아나운서), "
        "라디오 콘텐츠 공모전으로 확인."
    ),
    RoleDomain.LITERATURE: (
        "웹툰 글·그림 분리 모집(다음웹툰·대원씨아이), 대한민국 스토리 공모대전(개인·팀), 시나리오 공모전 팀 응모, 그림책 공동 "
        "창작, 출판 프로젝트의 편집·교정 담당으로 확인."
    ),
    RoleDomain.ACADEMIC: (
        "통계청 논문 공모전(개인 또는 3명 이하 팀)과 위비티 논문 공모전 가이드의 역할 분담(데이터 수집·선행연구·통계 "
        "모델링·교정), 계량·통계 분석 팀원 모집 글로 확인."
    ),
    RoleDomain.SCIENCE_ENGINEERING: (
        "임베디드SW경진대회·대학생 자율주행 경진대회·자작자동차 팀의 하드웨어/소프트웨어 분담(기계 설계·회로·ROS 자율주행), "
        "IoT 메이커톤, 캠퍼스 특허 유니버시아드(개인 또는 3인 이내 팀)로 확인."
    ),
    RoleDomain.ARCHITECTURE: (
        "목조건축대전·전통조경대전·실내건축대전 팀의 설계/모델링/패널 분담, 토목구조물 모형 경진대회, 엔지니어링산업 BIM 부문, "
        "건설관리학회 학생 경진대회(원가·공정관리)로 확인."
    ),
    RoleDomain.POLICY_SOCIETY: (
        "정책제안 공모전 팀 모집 글, 모의재판 경연대회(대법원 가인 법정변론, 개인정보보호, 국제인도법), 대한민국 열린 "
        "토론대회(2인 팀)로 확인."
    ),
    RoleDomain.BUSINESS_ECONOMY: (
        "창업경진대회·케이스 경진대회·리서치 리포트 대회, 한국은행 통화정책 경시대회(4명 1팀), 통상정책 토론대회·무역구제 "
        "논문대회, 국제통상 팀원 모집 글로 확인."
    ),
    RoleDomain.ARTS_PERFORMANCE: (
        "뮤지컬 동아리 모집(배우, 스탭: 기획·조명·음향·미술(의상·소품)), 밴드 세션 모집, 대학가요제·작사 공모전·음원 제작 "
        "공모, 치어리딩 대회(BE 데이터)로 확인."
    ),
    RoleDomain.COOKING_FOOD: (
        "대한민국 국제요리&제과 경연대회 종목(한식·세계요리·제과·떡/한과·바리스타·칵테일·외식프랜차이즈), 떡 경연대회, 식품 신제품 "
        "개발 대회(ECOTROPHELIA·K-Food), 레시피 공모전으로 확인."
    ),
    RoleDomain.FASHION_BEAUTY: (
        "패션 공모전의 패턴·실물 제작 필수 제출, 전국대학생패션연합회 디자인팀·기획팀 모집, 뷰티 대회 4개 "
        "분야(헤어·피부·메이크업·네일), 공연 팀의 분장 스태프로 확인."
    ),
    RoleDomain.SPORTS: (
        "대학 스포츠 동아리의 선수·매니저 모집, e스포츠 대학리그 코칭스태프 인정, 구단 서포터즈(실제 업무는 일반 마케팅·행사)로 "
        "확인."
    ),
    RoleDomain.EDUCATION: (
        "SW 교육기부단 팀, 교육청 진로 멘토링(대학생 멘토), 예비교사 수업 콘테스트, 유아교육과 활동지도 매체 경진대회로 확인."
    ),
    RoleDomain.SOCIAL_VOLUNTEER: (
        "해외봉사단 조직(기획·홍보·교육·공연·물품팀), 해외탐방 팀(4~8인), 유학생 버디·통역 가이드 봉사로 확인."
    ),
    RoleDomain.EVENT_FESTIVAL: (
        "축제 기획단(기획·대외협력(섭외·협찬후원)·운영·홍보·디자인), 축제 자원활동가(기획·무대·행사·홍보팀), 전시산업 대학생 "
        "경진대회(3~4인 팀)로 확인."
    ),
    RoleDomain.HEALTH_MEDICAL: (
        "디지털헬스 해커톤(의료인·기획자·개발자·디자이너 팀), 보건의료 창업경진대회 팀 모집, 의료계열 전공자 모집 글, 대학생 "
        "정신건강 서포터즈 영마인드(6~8인 팀)로 확인."
    ),
    RoleDomain.TRAVEL_CULTURE: (
        "관광상품 아이디어 공모전(4인 이하 팀), 관광두레 대학생 서포터즈(3인 팀), 서울 트립 어드바이저, 외국인 관광객 통역 "
        "가이드(YGG), 전시 도슨트 모집으로 확인."
    ),
}

_SOURCE_LINKS = [
    "위비티 공모전 분야: https://www.wevity.com/?c=find&s=1",
    "콘테스트코리아 대회·공모전/대외활동 분류: https://www.contestkorea.com/",
    "올콘 활동분야: https://www.all-con.co.kr/list/contest/1",
    "링커리어: BE가 수집한 공모전 데이터(`data/result_events.json`)의 분야 21개(`ContestField`)",
    "요리 세부 역할: 대한민국 국제요리&제과 경연대회 종목(한식요리, 세계요리, 제과, 떡/한과, 바리스타, "
    "칵테일, 테이블서비스, 외식프랜차이즈 등)",
    "역할 구성: 링커리어 팀원 모집 글, 대회 모집 요강, 대학 연합동아리 파트 구성(2026-11-05 확인, 도메인별 "
    "요약은 위 '역할 구성 근거')",
]


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def render_domain_doc() -> str:
    frozen = ", ".join(f"`{value}`" for value in FROZEN_ROLE_CODE_VALUES)
    role_counts = {domain: 0 for domain in ROLE_DOMAIN_LABELS}
    for domain in ROLE_DOMAINS.values():
        role_counts[domain] += 1

    lines = [
        "# 도메인 코드 목록",
        "",
        "AI 서버·FE·BE가 공통으로 쓰는 코드 값이다. 2026-11-05부터 FE·BE는 AI 서버의 정의를 따른다.",
        "",
        "이 파일은 `uv run python scripts/generate_domain_doc.py`로 코드에서 생성한다. 값을 바꾸려면",
        "`app/schemas/role_codes.py`, `app/schemas/activity.py`, `app/schemas/contest.py`를 고친 뒤",
        "다시 생성한다.",
        "",
        "- API로 주고받는 값은 코드 열이다. 한글 라벨은 화면 표시용이다.",
        f"- 역할은 공모전 도메인 {len(ROLE_DOMAIN_LABELS)}개 아래에 도메인별로 나뉘어 있다"
        f"(역할 {len(ROLE_CODE_LABELS)}개). 예를 들어 IT에는 백엔드·프론트엔드 개발이, 요리에는 한식·양식·"
        "중식·메뉴 기획이 있다.",
        "- 팀은 다른 도메인의 역할도 모집할 수 있다(예: 요리 공모전 팀이 `VIDEO_EDITING`을 모집).",
        "  도메인은 역할을 고르는 화면을 나누는 기준이지 제한이 아니다. 도메인 값은 API 요청·응답에 나오지 않는다.",
        f"- 처음부터 있던 역할 코드 10개({frozen})는 값이 그대로다.",
        "  각자 맞는 도메인에 들어갔고, 일부는 겹치는 의미를 새 코드로 떼어내 범위가 좁아졌다(예: AI는",
        "  `Data`에서 `IT_AI`로). 그 전에 저장된 값은 팀 임베딩 재계산(`/internal/teams/embedding:refresh`)과",
        "  의도 재추출(`/intents/extract`)로 다시 정규화해야 정확하다.",
        "",
        f"## 공모전 도메인 (`RoleDomain`, {len(ROLE_DOMAIN_LABELS)}개)",
        "",
        "여러 공모전·대외활동 사이트의 분야 분류를 합쳐 잡았다. 근거 열은 각 사이트의 분야 이름이다.",
        "",
        *_table(
            ["코드", "한글 라벨", "역할 수", "근거(사이트 분야 이름)"],
            [
                [f"`{domain.value}`", label, str(role_counts[domain]), _DOMAIN_SOURCES[domain]]
                for domain, label in ROLE_DOMAIN_LABELS.items()
            ],
        ),
        "",
        f"## 역할 (`RoleCode`, {len(ROLE_CODE_LABELS)}개)",
        "",
        "`desired_roles`(사용자), `recruiting_roles`(팀)에 쓰인다.",
        "",
        *_table(
            ["도메인", "코드", "한글 라벨"],
            [
                [ROLE_DOMAIN_LABELS[ROLE_DOMAINS[code]], f"`{code.value}`", label]
                for code, label in ROLE_CODE_LABELS.items()
            ],
        ),
        "",
        "## 역할 구성 근거",
        "",
        "도메인마다 실제 공모전 팀이 어떤 역할로 나뉘는지 확인한 자료다.",
        "",
        *[
            f"- **{ROLE_DOMAIN_LABELS[domain]}**: {sentence}"
            for domain, sentence in _ROLE_EVIDENCE.items()
        ],
        "",
        "## 공모전 분야 → 먼저 보여줄 역할 도메인",
        "",
        "BE 공모전 데이터의 분야(`ContestField`)에 딸린 팀이 주로 모집하는 도메인이다(앞에 올수록 많이",
        "모집한다). FE가 역할 선택 화면에서 어느 도메인을 먼저 보여줄지 정할 때 쓴다(제한 아님). 모든",
        "도메인이 최소 한 분야에 들어 있다.",
        "",
        *_table(
            ["공모전 분야", "역할 도메인"],
            [
                [
                    f"`{field.value}` {CONTEST_FIELD_LABELS[field]}",
                    ", ".join(ROLE_DOMAIN_LABELS[domain] for domain in domains),
                ]
                for field, domains in CONTEST_FIELD_DOMAINS.items()
            ],
        ),
        "",
        "## 경험 수준 (`ExperienceLevel`)",
        "",
        "분야와 무관하게 그 분야에서의 경험을 뜻한다.",
        "",
        *_table(
            ["코드", "한글 라벨"],
            [[f"`{level.value}`", label] for level, label in EXPERIENCE_LEVEL_LABELS.items()],
        ),
        "",
        "## 활동 방식 (`ActivityStyle`)",
        "",
        "`activity_style`에 쓰인다. 온라인·오프라인 여부만 나타내며, 협업 성향은 담지 않는다.",
        "",
        *_table(
            ["코드", "한글 라벨"],
            [[f"`{style.value}`", label] for style, label in ACTIVITY_STYLE_LABELS.items()],
        ),
        "",
        "## 공모전 구분 (`ContestCategory`)",
        "",
        *_table(
            ["코드", "한글 라벨"],
            [[f"`{category.value}`", label] for category, label in CONTEST_CATEGORY_LABELS.items()],
        ),
        "",
        f"## 공모전 분야 (`ContestField`, {len(CONTEST_FIELD_LABELS)}개)",
        "",
        "공모전 자체의 분류다(이미지 자동 입력·BE 공모전 데이터). 역할 도메인과는 별개다.",
        "",
        *_table(
            ["코드", "한글 라벨"],
            [[f"`{field.value}`", label] for field, label in CONTEST_FIELD_LABELS.items()],
        ),
        "",
        "## 참고한 분류",
        "",
        *[f"- {source}" for source in _SOURCE_LINKS],
        "",
    ]
    return "\n".join(lines)
