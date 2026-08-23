from pydantic import BaseModel, Field

from app.schemas.common import EmbeddingVector


class ContestSimilarityItem(BaseModel):
    """쿼리·후보 공모전이 공유하는 형태 — 둘 다 벡터(유사도 계산용)와 표시용 메타데이터가
    필요하다. `field`는 정규화된 `ContestField` 코드를 기대하지만, 코드가 아니어도(알 수 없는
    값이어도) 그대로 원문 echo만 하고 에러는 안 낸다 — field_label만 못 붙인다."""

    id: str
    embedding_vector: EmbeddingVector
    title: str
    organizer: str | None = None
    category: str | None = None
    field: str | None = None
    detail_url: str | None = None


class ContestSimilarityRequest(BaseModel):
    query: ContestSimilarityItem
    # 후보 선정은 항상 BE 책임이다 — AI 서버는 이 안에서 유사도 계산·정렬·top_n 컷·좌표 배치만
    # 한다("AI 서버는 후보 선정을 하지 않는다" 원칙, CLAUDE.md 참고).
    candidates: list[ContestSimilarityItem]
    top_n: int = Field(default=500, ge=1)


class ContestSimilarityPoint(BaseModel):
    id: str
    title: str
    organizer: str | None
    category: str | None
    field: str | None
    field_label: str | None
    detail_url: str | None
    similarity: float
    # 표시된 후보군 안에서의 순위 백분위(0=가장 유사, 1=가장 안 유사) — radius가 이 값으로
    # 정해진다. 절대 유사도(0~1)를 그대로 반지름에 매핑하면 실제 유사도가 좁은 대역에 몰려
    # 있을 때 대부분의 점이 바깥쪽에만 몰려 보이는 문제가 실측으로 있었다(CLAUDE.md 참고).
    rank_percentile: float
    radius: float
    x: float
    y: float


class ContestSimilarityReferenceRing(BaseModel):
    """절대 유사도가 아니라 백분위 기준 참고선 — "상위 10%가 실제로 어느 유사도 값부터인지"를
    같이 담아 화면에서 눈금처럼 쓸 수 있게 한다."""

    percentile: float
    similarity_at_percentile: float
    radius: float


class ContestSimilarityQueryEcho(BaseModel):
    id: str
    title: str
    organizer: str | None
    category: str | None
    field: str | None
    field_label: str | None
    detail_url: str | None


class ContestSimilarityResponse(BaseModel):
    query: ContestSimilarityQueryEcho
    points: list[ContestSimilarityPoint]
    max_radius: float
    min_radius: float
    radial_jitter: float
    reference_rings: list[ContestSimilarityReferenceRing]
    candidate_pool_total: int
