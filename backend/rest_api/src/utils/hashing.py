import secrets

from passlib.context import CryptContext
from src.core.config import settings
from src.utils.aiowrapper import aio

# All utilities for authentication
_bcrypt_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS
)

# A real hash of a value nobody knows, verified against when a sign-in names an
# account that does not exist. Comparing against *something* is what keeps the
# response time the same either way; skipping the comparison would answer "does
# this email have an account" with a stopwatch, which is the question the
# status codes were changed to stop answering.
#
# Generated at import with the configured cost, so it takes exactly as long to
# verify as a real password does. One bcrypt round at startup.
DUMMY_PASSWORD_HASH = _bcrypt_context.hash(secrets.token_urlsafe(32))


async def get_password_hash(password: str) -> str:
    return await aio(_bcrypt_context.hash)(password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return await aio(_bcrypt_context.verify)(plain_password, hashed_password)
