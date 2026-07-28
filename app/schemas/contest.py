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
