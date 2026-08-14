from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.channel.repository import ChannelRepository
from src.channel.schemas import DMChannelCreate
from src.database.core import get_db
from src.database.service import BaseService
from libs.db import FriendRequest
from src.friendship.repository import FriendshipRepository
from src.friendship.schemas import FriendRequestAccept, FriendRequestCreate
from src.realtime import events
from src.realtime.publisher import realtime_publisher
from libs.db import User


class FriendshipService(BaseService):
    async def create_friend_request(
        self, user: CurrentUser, to_username: str
    ) -> FriendRequest:
        async with self.db.begin():
            friend_request = await FriendshipRepository.create_friend_request(
                self.db,
                FriendRequestCreate(from_user_id=user.id, to_username=to_username),
            )

        await realtime_publisher.publish(
            events.friend_request_received(
                request_id=friend_request.id,
                from_user_id=user.id,
                from_username=user.name,
                to_user_id=friend_request.to_user_id,
            )
        )
        return friend_request

    async def get_friend_request_by_id(self, friend_request_id: str) -> FriendRequest:
        return await FriendshipRepository.get_friend_request_by_id(
            self.db, friend_request_id
        )

    async def get_friend_requests_by_user_id(self, user_id: str) -> list[FriendRequest]:
        return await FriendshipRepository.get_friend_requests_by_user_id(
            self.db, user_id
        )

    async def get_outgoing_friend_requests(self, user_id: str) -> list[FriendRequest]:
        return await FriendshipRepository.get_outgoing_friend_requests(
            self.db, user_id
        )

    async def accept_friend_request(
        self, user: CurrentUser, friend_request_id: str
    ) -> FriendRequestAccept:
        async with self.db.begin():
            friendship = await FriendshipRepository.accept_friend_request(
                self.db, user.id, friend_request_id
            )
            dm_channel = await ChannelRepository.create_dm_channel(
                self.db,
                DMChannelCreate(
                    user_id=str(friendship.user_1_id),
                    user_id2=str(friendship.user_2_id),
                ),
            )
            # The caller needs the new channel to update its store without a refetch
            friend_id = (
                str(friendship.user_2_id)
                if str(friendship.user_1_id) == str(user.id)
                else str(friendship.user_1_id)
            )
            accepted = FriendRequestAccept(
                friend_id=friend_id,
                dm_channel_id=str(dm_channel.id),
            )

        # Both sides just gained a channel, so both gateways must re-read
        await realtime_publisher.invalidate_user_channels(user.id, friend_id)
        await realtime_publisher.publish(
            events.friend_request_accepted(
                accepted_by_id=user.id,
                accepted_by_username=user.name,
                to_user_id=friend_id,
                dm_channel_id=accepted.dm_channel_id,
            ),
            events.channels_changed(
                actor_id=user.id,
                to_user_id=user.id,
                text="You have a new direct message channel",
                channel_id=accepted.dm_channel_id,
            ),
        )
        return accepted

    async def reject_friend_request(self, user_id: str, friend_request_id: str) -> bool:
        async with self.db.begin():
            return await FriendshipRepository.reject_friend_request(
                self.db, user_id, friend_request_id
            )

    async def get_user_friends(self, user_id: str) -> list[User]:
        return await FriendshipRepository.get_user_friends(self.db, user_id)


def get_friendship_service(db: AsyncSession = Depends(get_db)):
    return FriendshipService(db)
