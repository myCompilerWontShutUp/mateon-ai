from fastapi import FastAPI

from app.api.router import router

app = FastAPI(title="mateon-ai")
app.include_router(router)
