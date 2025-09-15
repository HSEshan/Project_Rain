from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.schemas import Token, UserCreate, UserResponse
from src.auth.utils import create_access_token, parse_login_method
from src.database.core import get_db
from src.database.service import BaseService
from src.user.models import User
from src.utils.exceptions import (
    AlreadyExistsException,
    NotFoundException,
    UnauthorizedException,
)
from src.utils.hashing import get_password_hash, verify_password


class AuthService(BaseService):

    async def get_user_by_id(self, user_id: str) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException("User not found")
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).filter(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).filter(User.username == username))
        return result.scalar_one_or_none()

    async def register_user(self, user: UserCreate) -> UserResponse:
        async with self.db.begin():
            user_exists = await self.get_user_by_email(user.email)
            if user_exists:
                raise AlreadyExistsException("User with this email already exists")
            user_exists = await self.get_user_by_username(user.username)
            if user_exists:
                raise AlreadyExistsException("User with this username already exists")

            user = User(
                email=user.email,
                username=user.username,
                password_hash=await get_password_hash(user.password),
            )
            self.db.add(user)
            await self.db.flush()
            await self.db.refresh(user)
        return UserResponse(id=str(user.id), username=user.username, email=user.email)

    async def login_user(self, form_data: OAuth2PasswordRequestForm) -> Token:
        login_method = parse_login_method(form_data.username)
        if login_method == "email":
            user_to_login = await self.get_user_by_email(form_data.username.lower())
        elif login_method == "username":
            user_to_login = await self.get_user_by_username(form_data.username)
        if not user_to_login:
            raise NotFoundException("User not found")
        if not await verify_password(
            plain_password=form_data.password,
            hashed_password=user_to_login.password_hash,
        ):
            raise UnauthorizedException("Invalid password")

        return await create_access_token(
            str(user_to_login.id),
            user_to_login.email,
            user_to_login.username,
        )

    async def delete_user(self, user_id: str):
        user = await self.get_user_by_id(user_id)
        await self.db.delete(user)
        await self.db.commit()
        return True


def get_auth_service(db: AsyncSession = Depends(get_db)):
    return AuthService(db)
