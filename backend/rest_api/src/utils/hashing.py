from passlib.context import CryptContext
from src.core.config import settings
from src.utils.aiowrapper import aio

# All utilities for authentication
_bcrypt_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS
)


async def get_password_hash(password: str) -> str:
    return await aio(_bcrypt_context.hash)(password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    return await aio(_bcrypt_context.verify)(plain_password, hashed_password)
