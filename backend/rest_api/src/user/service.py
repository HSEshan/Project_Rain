from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.core import get_db
from src.database.service import BaseService
from src.user.models import User
from src.user.repository import UserRepository
from src.user.schemas import BulkUserRequest, BulkUserResponse, UserResponse


class UserService(BaseService):
    async def get_user_by_id(self, user_id: str) -> User:
        return await UserRepository.get_user_by_id(self.db, user_id)

    async def get_user_by_username(self, username: str) -> User:
        return await UserRepository.get_user_by_username(self.db, username)

    async def get_users_by_ids(self, request: BulkUserRequest) -> BulkUserResponse:
        users = await UserRepository.get_users_by_ids(self.db, request.ids)
        return BulkUserResponse(
            users=[
                UserResponse(id=str(user.id), username=user.username) for user in users
            ]
        )


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)
