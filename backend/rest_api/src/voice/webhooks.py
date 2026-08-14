"""LiveKit webhook verification.

LiveKit signs each webhook with the same API secret we mint join tokens with:
the `Authorization` header is an HS256 JWT whose `sha256` claim is the base64
digest of the raw request body. Verifying both proves the call came from our
SFU and that the body was not altered, which matters because this endpoint is
the only thing that writes the voice roster.
"""

import base64
import hashlib

import structlog
from jose import JWTError, jwt

logger = structlog.get_logger()


class WebhookVerificationError(Exception):
    pass


def verify(*, api_key: str, api_secret: str, authorization: str | None, body: bytes):
    if not authorization:
        raise WebhookVerificationError("Missing Authorization header")

    # LiveKit sends the bare token, but tolerate a Bearer prefix
    token = authorization.removeprefix("Bearer ").strip()

    try:
        claims = jwt.decode(token, api_secret, algorithms=["HS256"])
    except JWTError as e:
        raise WebhookVerificationError(f"Bad webhook token: {e}") from e

    if claims.get("iss") != api_key:
        raise WebhookVerificationError("Webhook token was issued for another key")

    expected = claims.get("sha256")
    actual = base64.b64encode(hashlib.sha256(body).digest()).decode()
    if not expected or expected != actual:
        raise WebhookVerificationError("Webhook body does not match its signature")
