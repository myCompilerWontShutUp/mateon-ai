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

    # 공모전 이미지 업로드 크기 상한 (bytes). Vision 모델에 그대로 태워보내므로 과금/응답
    # 지연을 막기 위한 상한이다.
    max_contest_image_bytes: int = 10_000_000
    # 포트폴리오 PDF 업로드 크기 상한 (bytes).
    max_portfolio_pdf_bytes: int = 20_000_000
    # 포트폴리오 PDF에서 Vision 모델로 넘길 최대 페이지 수 — 페이지마다 이미지 1장이 추가
    # 비용으로 붙으므로, 아주 긴 PDF라도 앞부분만 본다.
    portfolio_pdf_max_pages: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
