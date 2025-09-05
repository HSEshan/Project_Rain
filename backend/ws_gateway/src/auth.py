import structlog
from fastapi import WebSocketException, status
from jose import JWTError, jwt
from pydantic import BaseModel
from src.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

logger = structlog.get_logger()


class CurrentUser(BaseModel):
    email: str
    name: str
    id: str
    exp: int


async def get_current_user_ws(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        name = payload.get("name")
        id = payload.get("id")
        exp = payload.get("exp")
        if not email or not id:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload"
            )
        return CurrentUser(id=str(id), name=name, email=email, exp=exp)
    except JWTError as e:
        logger.error(f"Error verifying user: {e}")
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Could not verify token"
        )
