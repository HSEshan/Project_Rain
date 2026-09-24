"""The session routes, without a database.

These are about the *cookie*, which is the half of refresh rotation that has no
other test: the rotation rules live in `AuthService` and are covered end to end
by `backend/tests/e2e/smoke.py` against a real stack, but nothing there can see
`HttpOnly` or the path, and both are load-bearing. A refresh cookie that the
browser will not send back, or that JavaScript can read, fails silently and in
production.
"""

from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from libs.db import generate_timestamp
from src.auth.cookies import (
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    SESSION_HINT_COOKIE,
)
from src.auth.schemas import Token
from src.auth.service import IssuedSession, get_auth_service
from src.auth.utils import generate_refresh_token, hash_refresh_token
from src.utils.exceptions import UnauthorizedException
from tests.conftest import override_dependency


class StubAuthService:
    def __init__(self, session: IssuedSession | None = None):
        self._session = session
        self.revoked = False

    async def rotate_session(self, raw_token):
        if self._session is None:
            raise UnauthorizedException("Session expired")
        return self._session

    async def revoke_session(self, raw_token):
        self.revoked = True


def a_session() -> IssuedSession:
    return IssuedSession(
        access_token=Token(access_token="signed.jwt.value", token_type="bearer"),
        refresh_token="the-new-refresh-token",
        refresh_expires_at=generate_timestamp(timedelta(days=30)),
    )


def set_cookie_header(response) -> str:
    """Every `Set-Cookie` on the response, joined.

    There is more than one: the refresh cookie the browser cannot read, and the
    readable marker that tells the client a session exists at all.
    """
    return "\n".join(response.headers.get_list("set-cookie"))


def test_refresh_returns_an_access_token_and_rotates_the_cookie(
    test_client: TestClient,
) -> None:
    override_dependency(get_auth_service, lambda: StubAuthService(a_session()))

    response = test_client.post(
        "/auth/refresh", cookies={REFRESH_COOKIE_NAME: "the-old-refresh-token"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["access_token"] == "signed.jwt.value"

    header = set_cookie_header(response)
    assert "the-new-refresh-token" in header
    # The three attributes that make it a refresh cookie rather than just a
    # cookie. Without HttpOnly, any script on the page can read the credential
    # that renews the session, which is the entire reason the session is split
    # in two.
    refresh_line = next(
        line for line in header.splitlines() if line.startswith(REFRESH_COOKIE_NAME)
    )
    assert "HttpOnly" in refresh_line
    assert f"Path={REFRESH_COOKIE_PATH}" in refresh_line
    assert "samesite=lax" in refresh_line.lower()

    # The marker is the opposite of the refresh cookie in every way that
    # matters: readable, path `/`, and worth nothing to whoever reads it.
    hint_line = next(
        line for line in header.splitlines() if line.startswith(SESSION_HINT_COOKIE)
    )
    assert "HttpOnly" not in hint_line
    assert "Path=/;" in hint_line or hint_line.rstrip().endswith("Path=/")


def test_a_refused_refresh_clears_the_cookie(test_client: TestClient) -> None:
    """401 has to take the dead token with it.

    FastAPI's exception handler builds its own response and drops the injected
    one, so a `raise` in the route would return 401 with the refused token
    still in the browser — and the client would present it again on the next
    reconnect, forever.
    """
    override_dependency(get_auth_service, lambda: StubAuthService(None))

    response = test_client.post(
        "/auth/refresh", cookies={REFRESH_COOKIE_NAME: "a-dead-token"}
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    header = set_cookie_header(response)
    assert REFRESH_COOKIE_NAME in header
    assert 'Max-Age=0' in header or 'expires=Thu, 01 Jan 1970' in header.lower()


def test_refresh_without_a_cookie_is_401(test_client: TestClient) -> None:
    """No cookie is a 401, not a 422. The route's only credential is optional
    at the FastAPI level precisely so that a missing one is answered by the
    service's own rule rather than by request validation."""
    override_dependency(get_auth_service, lambda: StubAuthService(None))

    response = test_client.post("/auth/refresh")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_revokes_and_clears(test_client: TestClient) -> None:
    stub = StubAuthService()
    override_dependency(get_auth_service, lambda: stub)

    response = test_client.post(
        "/auth/logout", cookies={REFRESH_COOKIE_NAME: "a-live-token"}
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert stub.revoked, "logout must revoke server-side, not just drop the cookie"
    assert REFRESH_COOKIE_NAME in set_cookie_header(response)


@pytest.mark.parametrize("_run", range(3))
def test_refresh_tokens_are_unique_and_hashed(_run: int) -> None:
    """The two properties the storage rule depends on: the value is random, and
    what the database sees is not the value."""
    token = generate_refresh_token()
    assert token != generate_refresh_token()

    digest = hash_refresh_token(token)
    assert len(digest) == 64, digest
    assert token not in digest
    assert digest == hash_refresh_token(token), "hashing must be deterministic"
