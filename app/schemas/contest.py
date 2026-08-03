from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class ContestCategory(StrEnum):
    CONTEST = "CONTEST"
    EXTERNAL = "EXTERNAL"
    SCHOOL = "SCHOOL"


class ContestField(StrEnum):
    TRAVEL_HOTEL_AIRLINE = "TRAVEL_HOTEL_AIRLINE"
    PRESS_MEDIA = "PRESS_MEDIA"
    CULTURE_HISTORY = "CULTURE_HISTORY"
    EVENT_FESTIVAL = "EVENT_FESTIVAL"
    EDUCATION = "EDUCATION"
    DESIGN_PHOTO_ART_VIDEO = "DESIGN_PHOTO_ART_VIDEO"
    ECONOMY_FINANCE = "ECONOMY_FINANCE"
    MANAGEMENT_CONSULTING_MARKETING = "MANAGEMENT_CONSULTING_MARKETING"
    POLITICS_SOCIETY_LAW = "POLITICS_SOCIETY_LAW"
    SPORTS_FITNESS = "SPORTS_FITNESS"
    MEDICAL_HEALTH = "MEDICAL_HEALTH"
    BEAUTY_COSMETICS = "BEAUTY_COSMETICS"
    SCIENCE_ENGINEERING_TECH_IT = "SCIENCE_ENGINEERING_TECH_IT"
    COOKING_FOOD = "COOKING_FOOD"
    STARTUP_SELF_DEVELOPMENT = "STARTUP_SELF_DEVELOPMENT"
    ENVIRONMENT_ENERGY = "ENVIRONMENT_ENERGY"
    CONTENTS = "CONTENTS"
    SOCIAL_CONTRIBUTION_EXCHANGE = "SOCIAL_CONTRIBUTION_EXCHANGE"
    DISTRIBUTION_LOGISTICS = "DISTRIBUTION_LOGISTICS"
    PLANNING_IDEA = "PLANNING_IDEA"
    ETC = "ETC"


# prompts/contest_image_extraction.txt에 이 21개 라벨이 하드코딩돼 있는 것과 별개로, 팀 임베딩
# 쪽(app/features/team_embedding/extraction.py)이 contest_field를 같은 ContestField로
# 정규화할 때 프롬프트 목록을 동적으로 만들기 위해 재사용한다 — 문자열을 두 번째로 손으로
# 옮겨 적지 않기 위함.
CONTEST_FIELD_LABELS: dict[ContestField, str] = {
    ContestField.TRAVEL_HOTEL_AIRLINE: "여행/호텔/항공",
    ContestField.PRESS_MEDIA: "언론/미디어",
    ContestField.CULTURE_HISTORY: "문화/역사",
    ContestField.EVENT_FESTIVAL: "행사/페스티벌",
    ContestField.EDUCATION: "교육",
    ContestField.DESIGN_PHOTO_ART_VIDEO: "디자인/사진/예술/영상",
    ContestField.ECONOMY_FINANCE: "경제/금융",
    ContestField.MANAGEMENT_CONSULTING_MARKETING: "경영/컨설팅/마케팅",
    ContestField.POLITICS_SOCIETY_LAW: "정치/사회/법률",
    ContestField.SPORTS_FITNESS: "체육/헬스",
    ContestField.MEDICAL_HEALTH: "의료/보건",
    ContestField.BEAUTY_COSMETICS: "뷰티/미용/화장품",
    ContestField.SCIENCE_ENGINEERING_TECH_IT: "과학/공학/기술/IT",
    ContestField.COOKING_FOOD: "요리/식품",
    ContestField.STARTUP_SELF_DEVELOPMENT: "창업/자기계발",
    ContestField.ENVIRONMENT_ENERGY: "환경/에너지",
    ContestField.CONTENTS: "콘텐츠",
    ContestField.SOCIAL_CONTRIBUTION_EXCHANGE: "사회공헌/교류",
    ContestField.DISTRIBUTION_LOGISTICS: "유통/물류",
    ContestField.PLANNING_IDEA: "기획/아이디어",
    ContestField.ETC: "기타",
}


class ContestExtractionResult(BaseModel):
    # 이미지에 공모전/대외활동/교내활동 공고로 볼 근거(제목, 주최, 모집 안내 등)가 전혀 없을 때
    # false — category/field/title은 스키마상 필수라 모델이 "모르겠다"를 표현할 방법이 이
    # 필드뿐이다. 없는 근거로 그럴듯한 공고를 지어내는 문제(백지/노이즈 이미지에도 실존하지
    # 않는 공모전 제목·URL을 생성)가 실제로 있어서 추가했다 — false면 나머지 필드는 신뢰하지
    # 말고 백엔드가 폐기/재업로드 요청 처리해야 한다.
    is_recognizable: bool = True
    # 이미지에 원본 공고 ID를 알아낼 단서(사이트명 워터마크, URL 등)가 없는 경우가 대부분이라
    # 선택 필드다 — 백엔드가 크롤링 메타데이터로 채우거나 비워둔다.
    external_id: str | None = Field(default=None, max_length=100)
    category: ContestCategory
    field: ContestField
    title: str = Field(max_length=255)
    organizer: str | None = Field(default=None, max_length=200)
    target_school: str | None = Field(default=None, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    detail_url: str | None = None
    image_url: str | None = None
    description: str | None = None
    summarized_description: str | None = Field(default=None, max_length=500)
    recommended_targets: str | None = None
