from typing import Annotated

from app.database.models.user import User
from app.schemas.users import UserCreate, UserDelete
from app.service.base import BaseService
from app.utils.exceptions import AlreadyExistsException, NotFoundException
from app.utils.password_manager import get_password_hash
from fastapi import Depends
from sqlalchemy import select


class UserService(BaseService):

    async def get_user_by_id(self, user_id: int) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException("User not found")
        return user

    async def get_user_by_email(self, email: str) -> User:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException("User not found")
        return user

    async def create_user(self, user: UserCreate) -> bool:
        user_by_email = await self.get_user_by_email(user.email)
        if user_by_email:
            raise AlreadyExistsException("User with this email already exists")
        user = User(
            email=user.email,
            username=user.username,
            password=get_password_hash(user.password),
        )
        self.db.add(user)
        try:
            await self.db.commit()
            await self.db.refresh(user)
            return True
        except Exception as e:
            raise e

    async def delete_user(self, user: UserDelete) -> bool:
        user = await self.get_user_by_email(user.email)
        if not user:
            raise NotFoundException("User not found")
        self.db.delete(user)
        await self.db.commit()
        return True


def get_user_service():
    return UserService()


user_service_dependency = Annotated[UserService, Depends(get_user_service)]
