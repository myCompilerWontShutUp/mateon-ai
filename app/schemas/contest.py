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
