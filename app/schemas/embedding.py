from pydantic import BaseModel, Field

from app.schemas.common import EmbeddingVector


class EmbeddingResult(BaseModel):
    embedding_text: str
    embedding_vector: EmbeddingVector
    metadata: dict = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
