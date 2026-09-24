from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from src.auth.cookies import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from src.auth.schemas import Token, UserCreate, UserResponse
from src.auth.service import AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(
    user: UserCreate, service: AuthService = Depends(get_auth_service)
):
    return await service.register_user(user)


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login_user(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: AuthService = Depends(get_auth_service),
):
    """The access token is the body; the refresh token is a cookie the page
    cannot read. See `src/auth/cookies.py` for why they are split."""
    session = await service.login_user(form_data)
    set_refresh_cookie(
        response, session.refresh_token, session.refresh_expires_at
    )
    return session.access_token


@router.post("/refresh", response_model=Token, status_code=status.HTTP_200_OK)
async def refresh_session(
    response: Response,
    rain_refresh: Annotated[Optional[str], Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    service: AuthService = Depends(get_auth_service),
):
    """Exchange the refresh cookie for a new access token, and rotate it.

    Takes no body and no `Authorization` header on purpose: an expired access
    token is the ordinary reason to be here, so requiring a live one would make
    the route useless exactly when it is needed. The cookie is the credential.

    Every failure is 401 with one message, and clears the cookie on the way
    out — a refresh token the server has refused is not going to start working,
    and leaving it in the browser means the client retries it forever.

    The failure path builds its own response rather than re-raising, because
    FastAPI's exception handler discards the injected `Response`: cookies set
    on it survive a returned value and vanish on a raise, so a `raise` here
    would leave the dead token exactly where it was.
    """
    try:
        session = await service.rotate_session(rain_refresh)
    except HTTPException as exc:
        failure = JSONResponse(
            status_code=exc.status_code, content={"detail": exc.detail}
        )
        clear_refresh_cookie(failure)
        return failure
    set_refresh_cookie(
        response, session.refresh_token, session.refresh_expires_at
    )
    return session.access_token


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    rain_refresh: Annotated[Optional[str], Cookie(alias=REFRESH_COOKIE_NAME)] = None,
    service: AuthService = Depends(get_auth_service),
):
    """Revoke the session server-side, then clear the cookie.

    Until this existed, signing out only deleted the client's copy of a token
    that stayed valid until it expired. It answers 204 whether or not there was
    anything to revoke: the caller cannot act on the difference, and a sign-out
    that can fail is one people learn to distrust.
    """
    await service.revoke_session(rain_refresh)
    clear_refresh_cookie(response)
