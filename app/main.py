from fastapi import FastAPI

from app.api.router import router
from app.core.config import Settings, get_settings
from app.features.contest_embedding.router import router as contest_embedding_router
from app.features.contest_extraction.router import router as contest_extraction_router
from app.features.contest_similarity.router import router as contest_similarity_router
from app.features.portfolio_summary.router import router as portfolio_summary_router
from app.features.quality.router import router as quality_router
from app.features.recommendation.router import router as recommendation_router
from app.features.team_embedding.router import router as team_embedding_router
from app.features.team_to_user.router import router as team_to_user_router
from app.features.user_to_team.router import router as user_to_team_router


def create_app(settings: Settings | None = None) -> FastAPI:
    # 설정을 앱 생성 시점에 읽는다 — 필수 환경변수(OPENAI_API_KEY, INTERNAL_SHARED_SECRET 등)가
    # 빠졌거나 비어 있으면 첫 요청이 아니라 서버 시작 시점에 바로 실패한다.
    settings = settings or get_settings()
    # /docs·/redoc·/openapi.json은 인증 없이 열리므로 운영에서는 기본으로 끈다
    # (Settings.api_docs_enabled). 계약 문서(docs/openapi.json)는 scripts/export_openapi.py가
    # app.openapi()로 따로 만든다.
    docs_enabled = settings.api_docs_enabled
    app = FastAPI(
        title="mateon-ai",
        description="Mate-On 팀 매칭 서비스의 AI 서버 — 무상태(stateless), 임베딩·스코어링·텍스트 생성 전담",
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.include_router(router)
    app.include_router(team_embedding_router)
    app.include_router(user_to_team_router)
    app.include_router(team_to_user_router)
    app.include_router(recommendation_router)
    app.include_router(contest_extraction_router)
    app.include_router(portfolio_summary_router)
    app.include_router(contest_similarity_router)
    app.include_router(contest_embedding_router)
    app.include_router(quality_router)
    return app


app = create_app()
