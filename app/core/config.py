from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str
    openai_llm_model: str = "gpt-5.6-luna"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # 기본값을 두지 않는다 — 배포 시 설정을 깜빡하면 다 아는 값으로 조용히 동작하는 대신
    # 시작 시점에 명확히 실패해야 한다.
    internal_shared_secret: str

    # LLM-as-judge 전용 모델. 생성 모델(openai_llm_model)과 의도적으로 분리한다 — 같은 모델이
    # 자기 출력을 검증하면 같은 맹점을 반복할 위험이 있어, GPT-5 이상급으로 승격하기로 했다
    # (CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 5번 참고). 기본값을 두지 않는다 —
    # 어떤 모델을 판정에 쓸지는 매번 명시적으로 골라야 하는 결정이라 조용히 기본값에 기대면 안 된다.
    openai_judge_model: str

    # 모니터링 텔레메트리(judge_results/cluster_selection_events/cluster_weight_config) 전용
    # Supabase 프로젝트. 도메인 데이터(팀/유저/임베딩/제안)는 여전히 저장하지 않는다 — 무상태
    # 원칙에 대한 좁은 예외다(CLAUDE.md 참고). service_role 키를 쓴다(RLS 우회, anon 키 아님).
    supabase_url: str
    supabase_service_role_key: str

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
