from fastapi import Depends
from libs.db import (
    Channel,
    ChannelMember,
    ChannelType,
    FriendRequest,
    Friendship,
    Guild,
    GuildMember,
    User,
)
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.core import get_db
from src.database.service import BaseService
from src.user.repository import UserRepository
from src.user.schemas import (
    BulkUserRequest,
    BulkUserResponse,
    FriendState,
    MutualGuild,
    UserProfile,
    UserResponse,
)


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

    async def get_profile(self, viewer_id: str, user_id: str) -> UserProfile:
        """The profile card: who they are, and who they are to the viewer.

        Everything here is scoped to the viewer. Mutual guilds are the guilds
        *both* are in, not that user's guild list, and the DM id is the one the
        viewer is a member of. Nothing tells the viewer about a relationship
        they are not part of.
        """
        user = await UserRepository.get_user_by_id(self.db, user_id)
        user_id = str(user.id)
        viewer_id = str(viewer_id)

        return UserProfile(
            id=user_id,
            username=user.username,
            created_at=user.created_at,
            friend_state=await self._friend_state(viewer_id, user_id),
            dm_channel_id=await self._shared_dm_channel_id(viewer_id, user_id),
            mutual_guilds=await self._mutual_guilds(viewer_id, user_id),
        )

    async def _friend_state(self, viewer_id: str, user_id: str) -> FriendState:
        if viewer_id == user_id:
            return FriendState.SELF

        # Friendship rows are stored with the ids sorted, so a single ordered
        # pair would miss half of them.
        friendship = await self.db.execute(
            select(Friendship).where(
                or_(
                    and_(
                        Friendship.user_1_id == viewer_id,
                        Friendship.user_2_id == user_id,
                    ),
                    and_(
                        Friendship.user_1_id == user_id,
                        Friendship.user_2_id == viewer_id,
                    ),
                )
            )
        )
        if friendship.scalar_one_or_none():
            return FriendState.FRIENDS

        request = await self.db.execute(
            select(FriendRequest).where(
                or_(
                    and_(
                        FriendRequest.from_user_id == viewer_id,
                        FriendRequest.to_user_id == user_id,
                    ),
                    and_(
                        FriendRequest.from_user_id == user_id,
                        FriendRequest.to_user_id == viewer_id,
                    ),
                )
            )
        )
        pending = request.scalars().first()
        if not pending:
            return FriendState.NONE
        return (
            FriendState.REQUEST_SENT
            if str(pending.from_user_id) == viewer_id
            else FriendState.REQUEST_RECEIVED
        )

    async def _shared_dm_channel_id(self, viewer_id: str, user_id: str) -> str | None:
        """The two-person DM they share, if there is one.

        Group DMs are excluded on purpose: "Message" on a profile card means a
        private conversation with that person, not the group you happen to both
        be in.
        """
        if viewer_id == user_id:
            return None

        mine = select(ChannelMember.channel_id).where(
            ChannelMember.user_id == viewer_id
        )
        theirs = select(ChannelMember.channel_id).where(
            ChannelMember.user_id == user_id
        )
        shared = await self.db.execute(
            select(Channel.id).where(
                Channel.type == ChannelType.DM,
                Channel.id.in_(mine),
                Channel.id.in_(theirs),
            )
        )
        channel_id = shared.scalars().first()
        return str(channel_id) if channel_id else None

    async def _mutual_guilds(
        self, viewer_id: str, user_id: str
    ) -> list[MutualGuild]:
        if viewer_id == user_id:
            return []

        mine = select(GuildMember.guild_id).where(GuildMember.user_id == viewer_id)
        theirs = select(GuildMember.guild_id).where(GuildMember.user_id == user_id)
        guilds = await self.db.execute(
            select(Guild.id, Guild.name).where(
                Guild.id.in_(mine), Guild.id.in_(theirs)
            )
        )
        return [
            MutualGuild(id=str(guild_id), name=name)
            for guild_id, name in guilds.all()
        ]


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)
