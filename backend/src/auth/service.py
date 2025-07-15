from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from src.auth.schemas import UserCreate, UserLogin
from src.auth.utils import create_access_token, parse_login_method
from src.database.service import BaseService
from src.user.models import User
from src.utils.exceptions import (
    AlreadyExistsException,
    NotFoundException,
    UnauthorizedException,
)
from src.utils.hashing import get_password_hash, verify_password


class AuthService(BaseService):
    async def get_user_by_username(self, username: str) -> User:
        result = await self.db.execute(select(User).where(User.username == username))
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

    async def register_user(self, user: UserCreate) -> bool:
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

    async def login_user(self, user: UserLogin):
        login_method = parse_login_method(user.login)
        if login_method == "email":
            user_by_email = await self.get_user_by_email(user.login)
            if not user_by_email:
                raise NotFoundException("User not found")
            if not verify_password(user.password, user_by_email.password):
                raise UnauthorizedException("Invalid password")
            return await create_access_token(
                user_by_email.id,
                user_by_email.email,
                user_by_email.username,
            )

        elif login_method == "username":
            user_by_username = await self.get_user_by_username(user.login)
            if not user_by_username:
                raise NotFoundException("User not found")
            if not verify_password(user.password, user_by_username.password):
                raise UnauthorizedException("Invalid password")
            return await create_access_token(
                user_by_username.id,
                user_by_username.email,
                user_by_username.username,
            )

        else:
            raise ValueError("Unprocessable entity")

    async def delete_user(self, user_id: int):
        user = await self.get_user_by_id(user_id)
        await self.db.delete(user)
        await self.db.commit()
        return True


def get_auth_service() -> AuthService:
    return AuthService()


auth_service = Annotated[AuthService, Depends(get_auth_service)]
