import structlog
from fastapi import WebSocketException, status
from jose import JWTError, jwt
from src.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

logger = structlog.get_logger()




async def get_current_user_ws(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        name = payload.get("name")
        id = payload.get("id")
        if not email or not id:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid token payload"
            )
        return {"email": email, "name": name, "id": id}
    except JWTError as e:
        logger.error(f"Error verifying user (WebSocket): {e}")
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Could not verify token"
        )