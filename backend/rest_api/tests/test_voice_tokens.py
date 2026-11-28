from datetime import timedelta

import pytest
from jose import jwt
from src.core.config import SettingsFactory, settings
from src.voice.tokens import create_join_token

SECRET = "test-livekit-secret"


def _issue() -> dict:
    token = create_join_token(
        api_key="devkey",
        api_secret=SECRET,
        room="room-1",
        user_id="user-1",
        username="alice",
    )
    return jwt.decode(token, SECRET, algorithms=["HS256"])


def test_ttl_setting_defaults_to_six_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVEKIT_TOKEN_TTL_SECONDS", raising=False)
    fresh = SettingsFactory(_env_file=None, **_required_fields())
    assert fresh.LIVEKIT_TOKEN_TTL_SECONDS == 6 * 60 * 60


def test_ttl_setting_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_TOKEN_TTL_SECONDS", "900")
    fresh = SettingsFactory(_env_file=None, **_required_fields())
    assert fresh.LIVEKIT_TOKEN_TTL_SECONDS == 900


def test_token_lifetime_is_default_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LIVEKIT_TOKEN_TTL_SECONDS", 6 * 60 * 60)
    claims = _issue()
    assert claims["exp"] - claims["nbf"] == int(timedelta(hours=6).total_seconds())


def test_token_lifetime_follows_configured_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LIVEKIT_TOKEN_TTL_SECONDS", 900)
    claims = _issue()
    assert claims["exp"] - claims["nbf"] == 900


def test_explicit_ttl_argument_still_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LIVEKIT_TOKEN_TTL_SECONDS", 900)
    token = create_join_token(
        api_key="devkey",
        api_secret=SECRET,
        room="room-1",
        user_id="user-1",
        username="alice",
        ttl=timedelta(minutes=1),
    )
    claims = jwt.decode(token, SECRET, algorithms=["HS256"])
    assert claims["exp"] - claims["nbf"] == 60


def _required_fields() -> dict:
    # Everything SettingsFactory requires, copied from the live settings so the
    # test does not depend on which env file the suite was started with.
    return {
        name: getattr(settings, name)
        for name, field in SettingsFactory.model_fields.items()
        if field.is_required()
    }
