from pydantic import BaseModel, Field


class EmbeddingResult(BaseModel):
    embedding_text: str
    embedding_vector: list[float]
    metadata: dict = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
