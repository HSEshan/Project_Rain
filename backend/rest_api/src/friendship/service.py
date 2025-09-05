from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.channel.repository import ChannelRepository
from src.channel.schemas import DMChannelCreate
from src.database.core import get_db
from src.database.service import BaseService
from src.friendship.models import FriendRequest
from src.friendship.repository import FriendshipRepository
from src.friendship.schemas import FriendRequestAccept, FriendRequestCreate
from src.user.models import User


class FriendshipService(BaseService):
    async def create_friend_request(
        self, friend_request: FriendRequestCreate
    ) -> FriendRequest:
        async with self.db.begin():
            friend_request = await FriendshipRepository.create_friend_request(
                self.db, friend_request
            )
        return friend_request

    async def get_friend_request_by_id(self, friend_request_id: str) -> FriendRequest:
        return await FriendshipRepository.get_friend_request_by_id(
            self.db, friend_request_id
        )

    async def accept_friend_request(
        self, user_id: str, friend_request_id: str
    ) -> FriendRequestAccept:
        async with self.db.begin():
            friendship = await FriendshipRepository.accept_friend_request(
                self.db, user_id, friend_request_id
            )
            dm_channel = await ChannelRepository.create_dm_channel(
                self.db,
                DMChannelCreate(
                    user_id=str(friendship.user_1_id),
                    user_id2=str(friendship.user_2_id),
                ),
            )
        return FriendRequestAccept(friendship=friendship, dm_channel=dm_channel)

    async def get_user_friends(self, user_id: str) -> list[User]:
        return await FriendshipRepository.get_user_friends(self.db, user_id)


def get_friendship_service(db: AsyncSession = Depends(get_db)):
    return FriendshipService(db)
