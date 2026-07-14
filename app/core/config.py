from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    openai_llm_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    database_url: str = "postgresql+asyncpg://mateon_ai:mateon_ai@localhost:5433/mateon_ai"


@lru_cache
def get_settings() -> Settings:
    return Settings()
