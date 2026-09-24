import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from src.auth.schemas import Token
from src.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# 48 bytes of `secrets`, which urlsafe-base64s to 64 characters. Long enough
# that the only way to hold one is to have been given it, which is what lets
# the database store a plain SHA-256 of it instead of a slow hash.
REFRESH_TOKEN_BYTES = 48


def generate_refresh_token() -> str:
    """The value the browser gets. It is never written down anywhere else."""
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(token: str) -> str:
    """What the database stores: hex SHA-256, so 64 characters exactly.

    Fast on purpose. bcrypt slows down guessing a secret a person chose; this
    secret is 48 random bytes, so there is nothing to guess and the only thing
    a slow hash would buy is ~60ms on every refresh in the app.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_access_token(
    id: str, email: str, name: str, expires_delta: timedelta | None = None
) -> Token:
    encode = {"sub": email, "id": id, "name": name}
    # 300 minutes until Phase 15, because the access token *was* the session:
    # nothing could renew it, so its lifetime was how long someone could use
    # the app. With rotation behind it the number means something narrower —
    # how long a copied access token keeps working — and it is configurable
    # rather than a literal buried in a default argument.
    lifetime = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)
    expire_time = datetime.now(timezone.utc) + lifetime
    encode.update({"exp": expire_time})

    token = jwt.encode(claims=encode, key=SECRET_KEY, algorithm=ALGORITHM)
    return Token(access_token=token, token_type="bearer")


class CurrentUser(BaseModel):
    email: str
    name: str
    id: str


async def get_current_user(
    token: Annotated[str, Depends(oauth2_bearer)],
) -> CurrentUser:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        name = payload.get("name")
        id = payload.get("id")
        if not email or not id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Token"
            )

        return CurrentUser(email=email, name=name, id=id)
    except JWTError as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not verify user"
        )


user_dependency = Annotated[CurrentUser, Depends(get_current_user)]


def parse_login_method(login: str) -> str:
    if "@" in login and "." in login:
        return "email"
    else:
        return "username"
