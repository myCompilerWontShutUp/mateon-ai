from fastapi import FastAPI

from app.api.router import router
from app.features.team_embedding.router import router as team_embedding_router

app = FastAPI(title="mateon-ai")
app.include_router(router)
app.include_router(team_embedding_router)
