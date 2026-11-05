"""Limits on the expensive and the guessable. Not a blanket limit on everything,
which mostly punishes normal use.

Each rule answers a specific cost: bcrypt on sign-in, an open registration form,
image decoding on upload, a write with nothing else bounding it. Rules are keyed
on the client address, on the account where there is one, or on both, because
each has a blind spot: an address is shared by everyone behind a NAT, and an
account only exists after authentication.

The numbers are deliberately generous. They are here to stop a script, and a
person who hits one has been done a disservice.
"""

import hashlib
import ipaddress
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from libs.rate_limit import RateLimit, hit
from src.auth.utils import user_dependency
from src.core.config import settings
from src.realtime.publisher import realtime_publisher
from src.utils.exceptions import RateLimitedException

LOGIN_IP = RateLimit("login:ip", 30, 60)
# Guessing one account from one address. Keyed on both, because keyed on the
# account alone it is a lever: two requests a minute from anywhere would keep the
# real owner locked out for as long as someone cared to run a script.
LOGIN_ACCOUNT_IP = RateLimit("login:account-ip", 10, 300)
# Across every address, so spreading a guess over a botnet does not help. High
# enough that one address, capped above at 120 an hour, cannot reach it alone.
LOGIN_ACCOUNT = RateLimit("login:account", 300, 3600)
REGISTER_IP = RateLimit("register:ip", 10, 3600)
# Per address, not per account: there is no authenticated user on this route,
# since an expired access token is the ordinary reason to be here.
REFRESH_IP = RateLimit("refresh:ip", 60, 60)
DEMO_IP = RateLimit("demo:ip", 20, 60)
UPLOAD_USER = RateLimit("upload:user", 30, 60)
UPLOAD_IP = RateLimit("upload:ip", 120, 60)
PROFILE_USER = RateLimit("profile:user", 20, 60)
MESSAGE_WRITE_USER = RateLimit("message-write:user", 30, 60)
# The last two are what stands between a code and someone guessing at them
INVITE_LINK_USER = RateLimit("invite-link:user", 20, 3600)
INVITE_PREVIEW_IP = RateLimit("invite-preview:ip", 60, 60)
INVITE_ACCEPT_USER = RateLimit("invite-accept:user", 30, 60)


def client_address(request: Request) -> str:
    """Who is really asking, as far as the edge can tell us.

    **`X-Real-IP`, and never `X-Forwarded-For`.** Nginx overwrites the former with
    the peer it actually saw, and Caddy passes it through; dev Caddy sets it the
    same way. The latter *appends* to whatever the client sent, so its leftmost
    entry is attacker-chosen, and a limit keyed on it is a limit the attacker
    resets at will. This is only sound because rest_api publishes no port: the
    edge is the only thing that can reach it.

    Falls back to the socket peer, which is the edge itself. Everyone then shares
    one bucket, which fails towards limiting too much rather than not at all.

    IPv6 is grouped by /64, because that is what one customer is handed. Keyed on
    the full address, one machine has 2^64 identities.
    """
    raw = request.headers.get("x-real-ip") or (
        request.client.host if request.client else "unknown"
    )
    try:
        address = ipaddress.ip_address(raw.strip())
    except ValueError:
        return raw
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False).network_address)
    return str(address)


async def enforce(rule: RateLimit, identity: str) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    decision = await hit(realtime_publisher.redis, rule, identity)
    if not decision.allowed:
        raise RateLimitedException(decision.retry_after)


def limit_ip(rule: RateLimit):
    """A route dependency: at most `rule` per client address."""

    async def dependency(request: Request) -> None:
        await enforce(rule, client_address(request))

    return dependency


def limit_user(rule: RateLimit):
    """A route dependency: at most `rule` per signed-in account."""

    async def dependency(user: user_dependency) -> None:
        await enforce(rule, str(user.id))

    return dependency


async def limit_login_account(
    request: Request,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> None:
    """Keyed on what was typed, whether or not such an account exists.

    Hashed so that Redis does not hold a list of email addresses, including every
    one anyone ever mistyped.
    """
    typed = form.username.strip().lower()
    account = hashlib.sha256(typed.encode()).hexdigest()[:32]
    await enforce(LOGIN_ACCOUNT_IP, f"{account}:{client_address(request)}")
    await enforce(LOGIN_ACCOUNT, account)

