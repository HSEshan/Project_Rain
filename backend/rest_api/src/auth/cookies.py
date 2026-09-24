"""Where the refresh token lives in a browser, and why it lives there.

**The access token and the refresh token are stored differently on purpose.**
The access token sits in a cookie JavaScript can read, and has to: the
websocket is opened as `/ws?token=...`, so the client needs the string in hand
(`WebsocketProvider`). The refresh token has no such requirement — it is only
ever sent back to `/api/auth/refresh` and `/api/auth/logout` — so it is
`httpOnly` and the page cannot read it at all. That is the whole reason for
splitting a session across two tokens rather than one long-lived one: the
credential that can renew a session is out of reach of anything that runs on
the page, and the one that is reachable expires in an hour.

Same-origin does the rest of the work. Caddy serves the app and proxies
`/api/*` to rest_api on one origin, so the cookie is a first-party cookie the
browser attaches on its own — no `withCredentials`, and no reliance on the
CORS configuration, which is `allow_origins=["*"]` and could not carry
credentials anyway.
"""

from datetime import datetime

from fastapi import Response
from src.core.config import ENVIRONMENT, settings

REFRESH_COOKIE_NAME = "rain_refresh"

# A readable marker that says "this browser has a session", and nothing else.
#
# It exists because the refresh cookie is unreadable by design, and the client
# needs to know whether asking is worth it. Without it the app has to attempt a
# refresh on every cold start to find out, including for the anonymous visitor
# who has just opened the public landing page — one wasted request and one 401
# in the console for everyone who has never signed in.
#
# It carries no value and authenticates nothing: it is written and cleared
# alongside the refresh cookie and with the same expiry, so the two cannot
# disagree, and forging it buys an attacker a 401 they could have had anyway.
SESSION_HINT_COOKIE = "rain_session"

# Scoped to the auth routes, so the token is not attached to every API request
# the app makes. The path is the one the *browser* uses: Caddy's `handle_path`
# strips `/api` before rest_api sees it, but cookie matching happens in the
# browser against the URL it requested. Change this and the refresh cookie
# silently stops being sent.
REFRESH_COOKIE_PATH = "/api/auth"


def _secure() -> bool:
    """`Secure` everywhere but development, which is served over plain http.

    Hard-coding `secure=True` would be the safer-looking choice and would break
    the dev stack completely: the browser would accept the cookie on
    `http://localhost:8080` and never send it back, so every refresh would fail
    with a missing token and no error anywhere explaining it.
    """
    return settings.ENVIRONMENT is not ENVIRONMENT.DEVELOPMENT


def set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    """Sets both cookies. They are written together so they cannot disagree."""
    set_session_hint(response, expires_at)
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        token,
        expires=expires_at,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=_secure(),
        # `lax` rather than `strict`: the app is same-origin so `strict` would
        # also work today, but `lax` is what keeps a refresh working when the
        # user arrives from a link somewhere else, and it is not a state-changing
        # GET that a third party could trigger.
        samesite="lax",
    )


def set_session_hint(response: Response, expires_at: datetime) -> None:
    """Readable on every path, because any page may need to ask."""
    response.set_cookie(
        SESSION_HINT_COOKIE,
        "1",
        expires=expires_at,
        path="/",
        httponly=False,
        secure=_secure(),
        samesite="lax",
    )


def clear_refresh_cookie(response: Response) -> None:
    """Must repeat path, secure and samesite: a delete only matches a cookie
    with the same attributes, and a mismatched one leaves the original in
    place while looking like it worked."""
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=_secure(),
        samesite="lax",
    )
    response.delete_cookie(
        SESSION_HINT_COOKIE,
        path="/",
        httponly=False,
        secure=_secure(),
        samesite="lax",
    )
