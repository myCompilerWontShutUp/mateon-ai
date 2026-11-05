import hmac

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_internal_secret(x_internal_secret: str = Header(...)) -> None:
    expected = get_settings().internal_shared_secret
    # 시크릿이 비어 있으면 아무 요청도 통과시키지 않는다(설정 검증이 먼저 막지만 한 번 더 막는다).
    # 비교는 상수 시간으로 해서 응답 시간 차이로 시크릿을 추측하지 못하게 한다.
    if not expected or not hmac.compare_digest(x_internal_secret.encode(), expected.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid internal secret")
