from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_internal_secret(x_internal_secret: str = Header(...)) -> None:
    settings = get_settings()
    if x_internal_secret != settings.internal_shared_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid internal secret")
