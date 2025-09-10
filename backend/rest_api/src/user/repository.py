import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.user.models import User
from src.utils.exceptions import NotFoundException

logger = structlog.get_logger(__name__)


class UserRepository:
    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> User:
        user = await db.execute(select(User).where(User.username == username))
        result = user.scalar_one_or_none()
        if not result:
            raise NotFoundException("User not found")
        return result

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
        user = await db.execute(select(User).where(User.id == user_id))
        result = user.scalar_one_or_none()
        if not result:
            raise NotFoundException("User not found")
        return result

    @staticmethod
    async def get_users_by_ids(db: AsyncSession, user_ids: list[str]) -> list[User]:
        users = await db.execute(select(User).where(User.id.in_(user_ids)))
        result = users.scalars().all()
        if not result:
            logger.error(f"Users not found: {user_ids}")
            raise NotFoundException(f"Users not found")
        return result
