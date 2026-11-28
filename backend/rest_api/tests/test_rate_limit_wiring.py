"""Which routes carry which limit, and that the login limits key the way they say.

`test_rate_limit.py` covers the limiter itself. A limit nobody attached does
nothing, and removing one from a route's `dependencies` is a one-line diff that
no other test would notice. The table below is AGENTS.md's list ("login
(address and account), register, refresh, demo login, uploads, PATCH /users/me
and websocket messages", plus the invite-link routes and message writes).
"""

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from main import app
from src.auth.schemas import Token
from src.auth.service import IssuedSession, get_auth_service
from src.core import rate_limit
from src.core.rate_limit import (
    DEMO_IP,
    INVITE_ACCEPT_USER,
    INVITE_LINK_USER,
    INVITE_PREVIEW_IP,
    LOGIN_ACCOUNT,
    LOGIN_ACCOUNT_IP,
    LOGIN_IP,
    MESSAGE_WRITE_USER,
    PROFILE_USER,
    REFRESH_IP,
    REGISTER_IP,
    UPLOAD_IP,
    UPLOAD_USER,
    limit_login_account,
)
from src.utils.exceptions import UnauthorizedException
from tests.conftest import override_dependency

EXPECTED = {
    ("POST", "/auth/register"): {REGISTER_IP.name},
    ("POST", "/auth/login"): {LOGIN_IP.name, "login-account"},
    ("POST", "/auth/refresh"): {REFRESH_IP.name},
    ("POST", "/demo/login"): {DEMO_IP.name},
    ("POST", "/guilds/{guild_id}/invite-links"): {INVITE_LINK_USER.name},
    ("GET", "/invites/{code}"): {INVITE_PREVIEW_IP.name},
    ("POST", "/invites/{code}/accept"): {INVITE_ACCEPT_USER.name},
    ("PATCH", "/messages/{message_id}"): {MESSAGE_WRITE_USER.name},
    ("DELETE", "/messages/{message_id}"): {MESSAGE_WRITE_USER.name},
    ("PATCH", "/users/me"): {PROFILE_USER.name},
    ("PUT", "/users/me/avatar"): {UPLOAD_IP.name, UPLOAD_USER.name},
    ("PUT", "/guilds/{guild_id}/icon"): {UPLOAD_IP.name, UPLOAD_USER.name},
    ("POST", "/uploads/attachments"): {UPLOAD_IP.name, UPLOAD_USER.name},
}


def rules_on(route: APIRoute) -> set[str]:
    """The rule names behind a route's dependencies, read from the closures
    `limit_ip` / `limit_user` return."""
    names = set()
    for dependant in route.dependant.dependencies:
        call = dependant.call
        if call is limit_login_account:
            names.add("login-account")
            continue
        for cell in getattr(call, "__closure__", None) or ():
            value = cell.cell_contents
            if isinstance(value, rate_limit.RateLimit):
                names.add(value.name)
    return names


def routes() -> dict[tuple[str, str], APIRoute]:
    table = {}
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                table[(method, route.path)] = route
    return table


@pytest.mark.parametrize("key", EXPECTED, ids=lambda k: f"{k[0]} {k[1]}")
def test_the_route_carries_its_limit(key):
    table = routes()
    assert key in table, f"{key} is not a route any more; update this table"
    assert rules_on(table[key]) == EXPECTED[key]


def test_every_rule_is_used_somewhere():
    used = set().union(*(rules_on(r) for r in routes().values()))
    defined = {
        value.name
        for value in vars(rate_limit).values()
        if isinstance(value, rate_limit.RateLimit)
    }
    # The account-wide login rules are applied inside `limit_login_account`
    defined -= {LOGIN_ACCOUNT.name, LOGIN_ACCOUNT_IP.name}
    assert defined <= used, f"defined but attached to nothing: {defined - used}"


# --------------------------------------------------------------------------
# Login keys, end to end through the route with a counting fake
# --------------------------------------------------------------------------


class CountingRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}

    async def eval(self, script, numkeys, key, window):
        self.counts[key] = self.counts.get(key, 0) + 1
        return [self.counts[key], window]


class WrongPassword:
    async def login_user(self, form):
        raise UnauthorizedException("Incorrect email or password")


class RightPassword:
    async def login_user(self, form):
        from datetime import timedelta

        from libs.db import generate_timestamp

        return IssuedSession(
            access_token=Token(access_token="t", token_type="bearer"),
            refresh_token="r",
            refresh_expires_at=generate_timestamp(timedelta(days=1)),
        )


@pytest.fixture()
def limited(monkeypatch):
    redis = CountingRedis()
    monkeypatch.setattr(rate_limit.realtime_publisher, "redis", redis)
    monkeypatch.setattr(rate_limit.settings, "RATE_LIMIT_ENABLED", True)
    return redis


def login(client: TestClient, who: str, ip: str):
    return client.post(
        "/auth/login",
        data={"username": who, "password": "Guess123!"},
        headers={"X-Real-IP": ip},
    )


def test_guessing_one_account_from_one_address_is_cut_off(limited, test_client):
    override_dependency(get_auth_service, lambda: WrongPassword())
    codes = [login(test_client, "victim@example.test", "198.51.100.1").status_code for _ in range(LOGIN_ACCOUNT_IP.limit + 1)]
    assert codes[:-1] == [401] * LOGIN_ACCOUNT_IP.limit
    assert codes[-1] == 429


def test_the_cutoff_does_not_lock_the_owner_out_from_their_own_address(limited, test_client):
    override_dependency(get_auth_service, lambda: WrongPassword())
    for _ in range(LOGIN_ACCOUNT_IP.limit + 1):
        login(test_client, "victim@example.test", "198.51.100.1")

    override_dependency(get_auth_service, lambda: RightPassword())
    assert login(test_client, "victim@example.test", "203.0.113.9").status_code == 200


def test_the_account_key_ignores_case_and_padding(limited, test_client):
    override_dependency(get_auth_service, lambda: WrongPassword())
    spellings = ["Victim@Example.test", " victim@example.test ", "VICTIM@EXAMPLE.TEST"]
    for i in range(LOGIN_ACCOUNT_IP.limit):
        login(test_client, spellings[i % len(spellings)], "198.51.100.1")
    assert login(test_client, "victim@example.test", "198.51.100.1").status_code == 429


def test_the_account_is_never_stored_in_the_clear(limited, test_client):
    override_dependency(get_auth_service, lambda: WrongPassword())
    login(test_client, "victim@example.test", "198.51.100.1")
    assert limited.counts
    assert not any("victim" in key for key in limited.counts)
