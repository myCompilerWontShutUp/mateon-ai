from enum import StrEnum
from typing import Annotated

from pydantic import Field


class MatchDirection(StrEnum):
    USER_TO_TEAM = "USER_TO_TEAM"
    TEAM_TO_USER = "TEAM_TO_USER"


# text-embedding-3-small 기준으로 확정된 값 (CLAUDE.md 참고). app.core.config.Settings.
# embedding_dimension과 같은 값을 유지해야 한다 — 여긴 Pydantic 필드 제약이라 상수여야 해서
# 별도로 정의한다.
EMBEDDING_DIMENSION = 1536

EmbeddingVector = Annotated[
    list[float], Field(min_length=EMBEDDING_DIMENSION, max_length=EMBEDDING_DIMENSION)
]
