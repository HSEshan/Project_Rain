"""Refresh rotation against a real table, and what an access token must be.

`test_sessions.py` covers the cookie with a stubbed service. This covers the
service: a token is spent once, its successor inherits the family's expiry, a
replay inside the grace window is served, a replay outside it revokes the whole
family, and logout ends the family rather than one token.

Concurrency (`FOR UPDATE`) is not reproducible on SQLite; the e2e suite has it.
"""

import base64
import json
from datetime import timedelta

import pytest
from fastapi import status
from jose import jwt
from libs.db import RefreshToken, User, generate_timestamp
from sqlalchemy import select, update
from src.auth.service import AuthService
from src.auth.utils import ALGORITHM, SECRET_KEY, create_access_token, hash_refresh_token
from src.core.config import settings
from src.utils.exceptions import UnauthorizedException
from tests.service_db import run, world


async def signed_in(w, name="alice"):
    person = await w.user(name)
    async with w.session() as db:
        row = await db.get(User, person.id)
        session = await AuthService(db).issue_session(row)
    return person, session


async def row_for(w, raw) -> RefreshToken | None:
    return await w.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw))
    )


async def rotate(w, raw):
    return await w.call(AuthService, "rotate_session", raw)


async def age_revocation(w, raw, seconds):
    async with w.session() as db:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(raw))
            .values(revoked_at=generate_timestamp(-timedelta(seconds=seconds)))
        )
        await db.commit()


def test_rotation_spends_the_token_and_the_successor_inherits_the_expiry():
    async def scenario():
        async with world() as w:
            person, first = await signed_in(w)
            second = await rotate(w, first.refresh_token)

            assert second.refresh_token != first.refresh_token
            old, new = await row_for(w, first.refresh_token), await row_for(w, second.refresh_token)
            assert old.revoked_at is not None
            assert new.revoked_at is None
            assert new.family_id == old.family_id
            # Absolute session lifetime, not sliding
            assert new.expires_at == old.expires_at
            assert second.refresh_expires_at == first.refresh_expires_at

            claims = jwt.decode(second.access_token.access_token, SECRET_KEY, algorithms=[ALGORITHM])
            assert claims["id"] == person.id

    run(scenario())


def test_the_database_never_holds_the_raw_token():
    async def scenario():
        async with world() as w:
            _, session = await signed_in(w)
            hashes = await w.scalars(select(RefreshToken.token_hash))
            assert session.refresh_token not in hashes
            assert hash_refresh_token(session.refresh_token) in hashes

    run(scenario())


@pytest.mark.parametrize("raw", [None, "", "never-issued"])
def test_missing_or_unknown_tokens_are_401(raw):
    async def scenario():
        async with world() as w:
            await signed_in(w)
            with pytest.raises(UnauthorizedException):
                await rotate(w, raw)

    run(scenario())


def test_an_expired_family_cannot_be_renewed():
    async def scenario():
        async with world() as w:
            _, session = await signed_in(w)
            async with w.session() as db:
                await db.execute(
                    update(RefreshToken).values(expires_at=generate_timestamp(-timedelta(seconds=1)))
                )
                await db.commit()
            with pytest.raises(UnauthorizedException):
                await rotate(w, session.refresh_token)

    run(scenario())


def test_a_replay_inside_the_grace_window_is_served_not_punished():
    async def scenario():
        async with world() as w:
            _, first = await signed_in(w)
            second = await rotate(w, first.refresh_token)
            # Another tab, same old cookie, a moment later
            third = await rotate(w, first.refresh_token)
            assert third.refresh_token not in (first.refresh_token, second.refresh_token)
            assert (await row_for(w, third.refresh_token)).revoked_at is None

    run(scenario())


def test_a_replay_after_the_grace_window_revokes_the_whole_family():
    async def scenario():
        async with world() as w:
            person, first = await signed_in(w)
            second = await rotate(w, first.refresh_token)
            await age_revocation(w, first.refresh_token, settings.REFRESH_REUSE_GRACE_SECONDS + 5)

            with pytest.raises(UnauthorizedException):
                await rotate(w, first.refresh_token)
            # The legitimate holder is signed out too: there is no telling who is who
            assert (await row_for(w, second.refresh_token)).revoked_at is not None
            with pytest.raises(UnauthorizedException):
                await rotate(w, second.refresh_token)

    run(scenario())


def test_reuse_in_one_family_does_not_touch_another_sign_in():
    async def scenario():
        async with world() as w:
            person, laptop = await signed_in(w)
            async with w.session() as db:
                phone = await AuthService(db).issue_session(await db.get(User, person.id))
            await rotate(w, laptop.refresh_token)
            await age_revocation(w, laptop.refresh_token, settings.REFRESH_REUSE_GRACE_SECONDS + 5)
            with pytest.raises(UnauthorizedException):
                await rotate(w, laptop.refresh_token)
            assert await rotate(w, phone.refresh_token)

    run(scenario())


def test_logout_ends_the_family_not_just_the_token():
    async def scenario():
        async with world() as w:
            _, first = await signed_in(w)
            second = await rotate(w, first.refresh_token)
            # Signing out with a stale token from the same family still ends it
            await w.call(AuthService, "revoke_session", first.refresh_token)
            with pytest.raises(UnauthorizedException):
                await rotate(w, second.refresh_token)
            # And is silent for nothing at all
            await w.call(AuthService, "revoke_session", None)
            await w.call(AuthService, "revoke_session", "never-issued")

    run(scenario())


def test_a_rotation_sweeps_that_users_expired_rows_only():
    async def scenario():
        async with world() as w:
            alice, a_session = await signed_in(w, "alice")
            bob, _ = await signed_in(w, "bob")
            async with w.session() as db:
                for owner in (alice, bob):
                    db.add(
                        RefreshToken(
                            user_id=owner.id,
                            token_hash=f"{owner.name}-dead".ljust(64, "0"),
                            expires_at=generate_timestamp(-timedelta(days=1)),
                        )
                    )
                await db.commit()
            await rotate(w, a_session.refresh_token)
            hashes = await w.scalars(select(RefreshToken.token_hash))
            assert "alice-dead".ljust(64, "0") not in hashes
            assert "bob-dead".ljust(64, "0") in hashes

    run(scenario())


# --------------------------------------------------------------------------
# The access token, at a route: no database is reached for any of these
# --------------------------------------------------------------------------


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_a_route_refuses_a_token_signed_with_another_key(test_client):
    forged = jwt.encode(
        {"sub": "a@example.test", "id": "x", "name": "a", "exp": generate_timestamp(timedelta(hours=1))},
        "not-the-secret",
        algorithm=ALGORITHM,
    )
    assert test_client.get("/channels/me", headers=bearer(forged)).status_code == 401


def test_a_route_refuses_an_expired_token(test_client):
    token = run(create_access_token("x", "a@example.test", "a", timedelta(seconds=-5)))
    assert test_client.get("/channels/me", headers=bearer(token.access_token)).status_code == 401


def test_a_route_refuses_an_alg_none_token(test_client):
    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    claims = {"sub": "a@example.test", "id": "x", "name": "a", "exp": 4102444800}
    unsigned = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}."
    assert test_client.get("/channels/me", headers=bearer(unsigned)).status_code == 401


def test_a_route_refuses_a_token_without_an_id(test_client):
    token = jwt.encode(
        {"sub": "a@example.test", "name": "a", "exp": generate_timestamp(timedelta(hours=1))},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    assert test_client.get("/channels/me", headers=bearer(token)).status_code == 401


def test_a_route_without_a_token_is_401(test_client):
    response = test_client.get("/channels/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
