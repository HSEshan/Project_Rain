"""LiveKit access tokens.

A LiveKit access token is an HS256 JWT signed with the API secret, carrying a
`video` grant that says which room the bearer may join and what they may do
there. We already sign our own JWTs with `python-jose`, so minting one here
costs nothing and keeps the LiveKit SDK (and its dependency tree) out of the
image. The claim shape is LiveKit's, not ours — do not "tidy" the camelCase
keys, the server matches them literally.

Identity is the user id: LiveKit enforces one connection per identity per room,
which is exactly the semantics we want for a voice channel. The username rides
along in `name` so other participants can render it without a lookup.
"""

import json
from datetime import datetime, timedelta, timezone

from jose import jwt
from src.core.config import settings


def token_ttl() -> timedelta:
    """The configured join-token lifetime (`LIVEKIT_TOKEN_TTL_SECONDS`, 6h by default)."""
    return timedelta(seconds=settings.LIVEKIT_TOKEN_TTL_SECONDS)


def create_join_token(
    *,
    api_key: str,
    api_secret: str,
    room: str,
    user_id: str,
    username: str,
    ttl: timedelta | None = None,
) -> str:
    if ttl is None:
        ttl = token_ttl()
    now = datetime.now(timezone.utc)
    claims = {
        "iss": api_key,
        "sub": user_id,
        "nbf": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "name": username,
        "metadata": json.dumps({"username": username}),
        "video": {
            "room": room,
            "roomJoin": True,
            "canSubscribe": True,
            "canPublish": True,
            "canPublishData": True,
            # Microphone and camera. Screen share is deliberately not here yet:
            # restricting sources server-side is what stops a modified client
            # publishing one, so adding it is a decision, not a UI change.
            "canPublishSources": ["microphone", "camera"],
        },
    }
    return jwt.encode(claims=claims, key=api_secret, algorithm="HS256")
