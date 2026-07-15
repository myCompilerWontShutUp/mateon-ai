from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    openai_llm_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # 기본값을 두지 않는다 — 배포 시 설정을 깜빡하면 다 아는 값으로 조용히 동작하는 대신
    # 시작 시점에 명확히 실패해야 한다.
    internal_shared_secret: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
