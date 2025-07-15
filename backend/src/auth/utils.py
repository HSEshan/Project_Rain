from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from src.auth.schemas import Token
from src.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/token")


async def create_access_token(
    id: int, email: str, name: str, expires_delta: timedelta
) -> Token:
    encode = {"sub": email, "id": id, "name": name}
    expire_time = datetime.now(timezone.utc) + expires_delta
    encode.update({"exp": expire_time})

    token = jwt.encode(claims=encode, key=SECRET_KEY, algorithm=ALGORITHM)
    return Token(access_token=token, token_type="bearer")


async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        name = payload.get("name")
        id = payload.get("id")
        if not email or not id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Token"
            )

        return {"email": email, "name": name, "id": id}
    except JWTError as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not verify user"
        )


user_dependency = Annotated[dict, Depends(get_current_user)]


def parse_login_method(login: str) -> str:
    if "@" in login and "." in login:
        return "email"
    else:
        return "username"
