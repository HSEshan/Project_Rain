from fastapi import Depends, UploadFile
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
from src.media.images import ImageKind
from src.media.service import store_image
from src.media.storage import delete_quietly
from src.realtime import events
from src.realtime.publisher import realtime_publisher
from src.user.repository import UserRepository
from src.user.schemas import (
    BulkUserRequest,
    BulkUserResponse,
    FriendState,
    MutualGuild,
    UserProfile,
    UserResponse,
    UserUpdate,
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
                UserResponse(
                    id=str(user.id),
                    username=user.username,
                    avatar_url=user.avatar_url,
                )
                for user in users
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
            avatar_url=user.avatar_url,
            bio=user.bio,
            created_at=user.created_at,
            friend_state=await self._friend_state(viewer_id, user_id),
            dm_channel_id=await self._shared_dm_channel_id(viewer_id, user_id),
            mutual_guilds=await self._mutual_guilds(viewer_id, user_id),
        )

    async def update_me(self, user_id: str, update: UserUpdate) -> UserProfile:
        """Edit your own profile. There is no route that edits anyone else's.

        The authorisation is the absence of a parameter: the id comes from the
        token and the path is `/users/me`, so there is no user id to get wrong
        and no ownership check to forget. A route shaped `PATCH /users/{id}`
        would need one, and would be one missing `if` away from letting anyone
        rewrite anyone.

        Only fields the caller actually named are touched. `model_fields_set`
        is the difference between "clear my bio" and "I sent you an avatar and
        said nothing about my bio", which are the same JSON once pydantic has
        filled the default in.
        """
        async with self.db.begin():
            user = await UserRepository.get_user_by_id(self.db, user_id)
            if "bio" in update.model_fields_set:
                user.bio = update.bio

        # Returned as a full profile so the client can drop it straight into the
        # store it already renders from. rest_api excludes the actor from the
        # events it publishes, so this response *is* how the person who made the
        # change finds out it worked — there is no event coming.
        return await self.get_profile(user_id, user_id)

    async def set_avatar(self, user_id: str, upload: UploadFile) -> UserProfile:
        """Replace your avatar. Same `me`-only shape as `update_me`.

        The new object is written first and the old one deleted only after the
        row points at the new one, so there is no moment where the avatar URL
        names nothing. The old key is deleted rather than kept: keys are never
        reused, so an old avatar nobody references is only storage cost.
        """
        key, _ = await store_image(upload, ImageKind.AVATAR, f"avatars/{user_id}")
        return await self._swap_avatar(user_id, key)

    async def clear_avatar(self, user_id: str) -> UserProfile:
        return await self._swap_avatar(user_id, None)

    async def _swap_avatar(self, user_id: str, key: str | None) -> UserProfile:
        async with self.db.begin():
            user = await UserRepository.get_user_by_id(self.db, user_id)
            old_key, user.avatar_key = user.avatar_key, key
            avatar_url = user.avatar_url
        # Read after the commit rather than inside the transaction that holds
        # the user row: the scan can be large, and the publish is after the
        # commit anyway, so there is no consistency to gain by holding the lock.
        audience = await self._people_who_see(user_id)
        await delete_quietly([old_key])
        # After the commit, like every publish in rest_api. The audience is
        # everyone who shares a channel with this person, which covers friends
        # (accepting a request creates the DM) and fellow guild members, and
        # includes the person themselves for their other tabs.
        await realtime_publisher.publish_many(
            events.user_updated(
                actor_id=user_id, to_user_id=member_id, avatar_url=avatar_url
            )
            for member_id in audience
        )
        return await self.get_profile(user_id, user_id)

    async def _people_who_see(self, user_id: str) -> list[str]:
        """Everyone in at least one channel with this user, them included.

        One row per person however
        many channels they share, so a busy guild costs one event each.
        """
        shared = select(ChannelMember.channel_id).where(
            ChannelMember.user_id == user_id
        )
        result = await self.db.execute(
            select(ChannelMember.user_id)
            .where(ChannelMember.channel_id.in_(shared))
            .distinct()
        )
        people = {str(member_id) for member_id in result.scalars()}
        people.add(str(user_id))
        return sorted(people)

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
