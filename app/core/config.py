from functools import lru_cache

from openai.types.shared import ReasoningEffort
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 빈 값은 "설정 안 됨"으로 본다(env_ignore_empty) — .env.example을 복사하고 값을 안 채우면 빈
    # 문자열이 들어오는데, 그대로 받으면 서버가 뜨고 빈 X-Internal-Secret 헤더가 인증을 통과했다
    # (2026-11-05 확인). 필수 값은 min_length=1까지 걸어 공백만 있는 값도 시작 시점에 막는다.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
        str_strip_whitespace=True,
    )

    openai_api_key: str = Field(min_length=1)
    openai_llm_model: str = "gpt-6-luna"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # 기본값을 두지 않는다 — 배포 시 설정을 깜빡하면 다 아는 값으로 조용히 동작하는 대신
    # 시작 시점에 명확히 실패해야 한다.
    internal_shared_secret: str = Field(min_length=1)

    # LLM-as-judge 전용 모델. 생성 모델(openai_llm_model)과 의도적으로 분리한다 — 같은 모델이
    # 자기 출력을 검증하면 같은 맹점을 반복할 위험이 있어, GPT-5 이상급으로 승격하기로 했다
    # (CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 5번 참고). 기본값을 두지 않는다 —
    # 어떤 모델을 판정에 쓸지는 매번 명시적으로 골라야 하는 결정이라 조용히 기본값에 기대면 안 된다.
    openai_judge_model: str = Field(min_length=1)

    # 모니터링 텔레메트리(judge_results/cluster_selection_events/cluster_weight_config) 전용
    # Supabase 프로젝트. 도메인 데이터(팀/유저/임베딩/제안)는 여전히 저장하지 않는다 — 무상태
    # 원칙에 대한 좁은 예외다(CLAUDE.md 참고). service_role 키를 쓴다(RLS 우회, anon 키 아님).
    supabase_url: str = Field(min_length=1)
    supabase_service_role_key: str = Field(min_length=1)

    # 공모전 이미지 업로드 크기 상한 (bytes). Vision 모델에 그대로 태워보내므로 과금/응답
    # 지연을 막기 위한 상한이다.
    max_contest_image_bytes: int = 10_000_000
    # 포트폴리오 PDF 업로드 크기 상한 (bytes).
    max_portfolio_pdf_bytes: int = 20_000_000
    # 포트폴리오 PDF에서 Vision 모델로 넘길 최대 페이지 수 — 페이지마다 이미지 1장이 추가
    # 비용으로 붙으므로, 아주 긴 PDF라도 앞부분만 본다.
    portfolio_pdf_max_pages: int = 15

    # 생성 모델의 추론 강도(reasoning_effort). 비워 두면 모델 기본값을 쓴다(gpt-6-luna는 medium).
    # 추론 토큰은 출력 토큰으로 과금되고 응답도 늦추므로, 운영에서 지연·비용이 문제면 "low" 등으로
    # 낮춘다. 판정 모델에는 적용하지 않는다(판정은 정확도가 우선). 허용 값은 OpenAI SDK의
    # ReasoningEffort(none/minimal/low/medium/high/xhigh/max)다 — 오타는 시작 시점에 막힌다. 모델이
    # 지원하지 않는 값이면 첫 생성 호출이 400으로 실패한다.
    openai_reasoning_effort: ReasoningEffort | None = None

    # 생성 텍스트(추천 사유·제안서)를 LLM-as-judge로 판정할 비율. 판정 모델이 생성 모델보다 단가가
    # 10배 높고 판정 입력도 더 길어서, 전수 판정하면 판정 비용이 생성 비용의 약 20배가 된다
    # (2026-11-05 계산). 설계(CLAUDE.md "## 모니터링·데이터 기반 가중치 보정" 5번)대로 표본 감사한다
    # — 무작위 표본이라 실패율 추이는 그대로 추정된다. 1.0이면 전수 판정.
    judge_sample_rate: float = Field(default=0.2, ge=0.0, le=1.0)

    # /docs, /redoc, /openapi.json 노출 여부. 운영 서버에서는 인증 없이 API 구조가 드러나지 않게
    # 기본으로 끈다(엔드포인트 자체는 X-Internal-Secret이 필요하다). 로컬 개발에서는 .env에서 켠다.
    # 계약 문서용 docs/openapi.json 생성은 이 값과 무관하게 app.openapi()로 만든다.
    api_docs_enabled: bool = False

    # Supabase에서 읽는 튜닝 설정값(cluster_weight_config)을 프로세스 안에 캐시해 둘 시간(초).
    # 추천 요청마다 같은 표를 다시 읽지 않기 위함이다. 값을 바꾼 뒤 늦어도 이 시간 안에 반영된다.
    config_cache_seconds: int = Field(default=60, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
