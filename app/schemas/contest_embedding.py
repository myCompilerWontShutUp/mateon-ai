from pydantic import BaseModel

from app.schemas.common import EmbeddingVector


class ContestEmbeddingRefreshRequest(BaseModel):
    # BE가 자체 채번한 공모전 ID를 그대로 돌려받기 위해서만 echo한다 — AI 서버는 이 값의 의미를
    # 해석하거나 저장하지 않는다(무상태 원칙 그대로).
    event_id: int
    title: str
    description: str


class ContestEmbeddingResult(BaseModel):
    event_id: int
    embedding_vector: EmbeddingVector
