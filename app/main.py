from fastapi import FastAPI

from app.api.router import router
from app.features.recommendation.router import router as recommendation_router
from app.features.team_embedding.router import router as team_embedding_router
from app.features.team_to_user.router import router as team_to_user_router
from app.features.user_to_team.router import router as user_to_team_router

app = FastAPI(
    title="mateon-ai",
    description="Mate-On 팀 매칭 서비스의 AI 서버 — 무상태(stateless), 임베딩·스코어링·텍스트 생성 전담",
    version="0.1.0",
)
app.include_router(router)
app.include_router(team_embedding_router)
app.include_router(user_to_team_router)
app.include_router(team_to_user_router)
app.include_router(recommendation_router)
