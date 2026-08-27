from fastapi import Depends
from libs.db import (
    MAX_GROUP_DM_MEMBERS,
    Channel,
    ChannelMember,
    ChannelType,
    GuildMember,
    GuildMemberRole,
    Message,
    User,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.channel.repository import ChannelRepository
from src.channel.schemas import (
    ChannelMemberResponse,
    ChannelMembers,
    DMChannelCreate,
    GroupDMCreate,
    GroupDMMemberAdd,
    GroupDMUpdate,
    GuildChannelCreate,
)
from src.database.core import get_db
from src.database.service import BaseService
from src.friendship.repository import FriendshipRepository
from src.realtime import events
from src.realtime.publisher import realtime_publisher
from src.utils.exceptions import (
    AlreadyExistsException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)


class ChannelService(BaseService):
    async def create_dm_channel(
        self, user: CurrentUser, channel_create: DMChannelCreate
    ) -> Channel:
        if str(user.id) not in (
            str(channel_create.user_id),
            str(channel_create.user_id2),
        ):
            raise ForbiddenException("You cannot create a DM you are not part of")

        async with self.db.begin():
            new_channel = await ChannelRepository.create_dm_channel(
                self.db, channel_create
            )

        return new_channel

    async def create_guild_channel(
        self, user: CurrentUser, guild_id: str, channel_create: GuildChannelCreate
    ) -> Channel:
        async with self.db.begin():
            # Only guild admins may add channels
            guild_member = await self.db.execute(
                select(GuildMember).where(
                    GuildMember.guild_id == guild_id, GuildMember.user_id == user.id
                )
            )
            result = guild_member.scalar_one_or_none()
            if not result or result.role != GuildMemberRole.ADMIN:
                raise ForbiddenException("You are not an admin of this guild")

            new_channel = Channel(
                name=channel_create.name,
                type=channel_create.type,
                guild_id=guild_id,
                description=channel_create.description,
            )
            self.db.add(new_channel)
            await self.db.flush()
            await self.db.refresh(new_channel)

            # Every guild member gets membership of the new channel
            guild_member_ids = await self.db.execute(
                select(GuildMember.user_id).where(GuildMember.guild_id == guild_id)
            )
            member_ids = [str(member_id) for member_id in guild_member_ids.scalars()]
            self.db.add_all(
                [
                    ChannelMember(channel_id=new_channel.id, user_id=member_id)
                    for member_id in member_ids
                ]
            )
            await self.db.flush()
            channel_id = str(new_channel.id)

        # Every member's channel list just changed
        await realtime_publisher.invalidate_user_channels(*member_ids)
        await realtime_publisher.publish_many(
            events.channels_changed(
                actor_id=user.id,
                to_user_id=member_id,
                text=f"New channel: {new_channel.name}",
                guild_id=guild_id,
                channel_id=channel_id,
            )
            for member_id in member_ids
        )
        return new_channel

    async def get_channel_by_id(self, user: CurrentUser, channel_id: str) -> Channel:
        await ChannelRepository.check_channel_member(self.db, user.id, channel_id)
        channel = await self.db.execute(select(Channel).where(Channel.id == channel_id))
        result = channel.scalar_one_or_none()
        if not result:
            raise NotFoundException("Channel not found")
        return result

    async def get_user_channels(self, user: CurrentUser) -> list[Channel]:
        return await ChannelRepository.get_user_channels(self.db, user.id)

    async def get_channel_participants(
        self, user: CurrentUser, channel_ids: list[str]
    ) -> dict[str, list[str]]:
        return await ChannelRepository.get_channel_participants(
            self.db, user.id, channel_ids
        )

    # ------------------------------------------------------------------
    # Group DMs
    #
    # A group DM is a channel with a mutable member list and no guild behind
    # it, which means no roles and no moderation. The only brake on who ends up
    # in one is that **you can only add your own friends** — the same rule at
    # creation and at every later add. Without it a group DM is an unsolicited
    # room anyone can pull a stranger into, and there is no moderator to remove
    # them.
    # ------------------------------------------------------------------

    async def create_group_dm(
        self, user: CurrentUser, group_create: GroupDMCreate
    ) -> Channel:
        member_ids = [str(user_id) for user_id in group_create.user_ids]
        if str(user.id) in member_ids:
            raise BadRequestException("You are already in the group")

        async with self.db.begin():
            for member_id in member_ids:
                await self._require_friend(user.id, member_id)

            channel = Channel(
                type=ChannelType.GROUP_DM,
                name=group_create.name,
                owner_id=str(user.id),
            )
            self.db.add(channel)
            await self.db.flush()
            await self.db.refresh(channel)

            # The creator first, so they are the longest-standing member and
            # inherit nothing when they leave: the next oldest does.
            self.db.add_all(
                [
                    ChannelMember(channel_id=channel.id, user_id=member_id)
                    for member_id in [str(user.id)] + member_ids
                ]
            )
            await self.db.flush()
            channel_id = str(channel.id)
            channel_name = channel.name

        await realtime_publisher.invalidate_user_channels(str(user.id), *member_ids)
        await realtime_publisher.publish_many(
            events.channels_changed(
                actor_id=user.id,
                to_user_id=member_id,
                text=f"{user.name} added you to {channel_name or 'a group'}",
                channel_id=channel_id,
            )
            for member_id in member_ids
        )
        return channel

    async def add_group_dm_member(
        self, user: CurrentUser, channel_id: str, member_add: GroupDMMemberAdd
    ) -> ChannelMembers:
        new_member_id = str(member_add.user_id)

        async with self.db.begin():
            channel = await self._require_group_dm(user, channel_id)
            await self._require_friend(user.id, new_member_id)

            existing = await ChannelRepository.get_channel_member_ids(
                self.db, channel_id
            )
            if new_member_id in existing:
                raise AlreadyExistsException("They are already in this group")
            if len(existing) >= MAX_GROUP_DM_MEMBERS:
                raise BadRequestException(
                    f"A group can hold {MAX_GROUP_DM_MEMBERS} people"
                )

            await ChannelRepository.add_user_to_channel(
                self.db, channel_id, new_member_id
            )
            channel_name = channel.name
            added_username = await self._username(new_member_id)

        # The new member's own membership changed, so their channel list and the
        # gateway's routing for them are both stale. The people already in the
        # channel only need its member list again.
        await realtime_publisher.invalidate_user_channels(new_member_id)
        await realtime_publisher.publish(
            events.channels_changed(
                actor_id=user.id,
                to_user_id=new_member_id,
                text=f"{user.name} added you to {channel_name or 'a group'}",
                channel_id=channel_id,
            )
        )
        await self._notify_members(
            actor=user,
            channel_id=channel_id,
            text=f"{user.name} added {added_username}",
            exclude={new_member_id},
        )
        return await self.get_channel_members(user, channel_id)

    async def leave_group_dm(self, user: CurrentUser, channel_id: str) -> None:
        """Leaving is the only way out; nobody can remove anybody else.

        That is deliberate. A group DM has no roles, so any "remove" power
        would be held equally by everyone in the room, and the first argument
        would end with people ejecting each other.
        """
        async with self.db.begin():
            await self._require_group_dm(user, channel_id)
            await ChannelRepository.remove_user_from_channel(
                self.db, channel_id, str(user.id)
            )
            remaining = await ChannelRepository.get_channel_member_ids(
                self.db, channel_id
            )
            emptied = not remaining
            if emptied:
                # Nobody can ever reach this channel again, and its messages
                # are unreachable with it. Leaving the rows behind would be an
                # unbounded, permanently orphaned table.
                await self._delete_channel(channel_id)
            else:
                await self._reassign_owner_if_needed(channel_id, remaining)

        await realtime_publisher.invalidate_user_channels(str(user.id))
        await realtime_publisher.publish(
            events.channels_changed(
                actor_id=user.id,
                to_user_id=str(user.id),
                text="You left the group",
                channel_id=channel_id,
            )
        )
        if not emptied:
            await self._notify_members(
                actor=user,
                channel_id=channel_id,
                text=f"{user.name} left the group",
            )

    async def update_group_dm(
        self, user: CurrentUser, channel_id: str, update: GroupDMUpdate
    ) -> Channel:
        async with self.db.begin():
            channel = await self._require_group_dm(user, channel_id)
            # Any member may rename it, the way Discord does: there is no
            # hierarchy here, and the owner only exists to inherit the room.
            channel.name = (update.name or "").strip() or None
            await self.db.flush()
            await self.db.refresh(channel)
            channel_name = channel.name

        await self._notify_members(
            actor=user,
            channel_id=channel_id,
            text=f"{user.name} renamed the group to {channel_name}"
            if channel_name
            else f"{user.name} cleared the group name",
        )
        return channel

    async def get_channel_members(
        self, user: CurrentUser, channel_id: str
    ) -> ChannelMembers:
        """The full member list, including the caller.

        `get_channel_participants` deliberately excludes the caller because it
        exists to title a DM. A group DM needs the real roster.
        """
        await ChannelRepository.check_channel_member(self.db, user.id, channel_id)
        channel = await self._get_channel(channel_id)
        members = await ChannelRepository.get_channel_members_with_usernames(
            self.db, channel_id
        )
        owner_id = str(channel.owner_id) if channel.owner_id else None
        return ChannelMembers(
            channel_id=str(channel_id),
            members=[
                ChannelMemberResponse(
                    user_id=user_id,
                    username=username,
                    is_owner=user_id == owner_id,
                )
                for user_id, username in members
            ],
        )

    async def _require_group_dm(self, user: CurrentUser, channel_id: str) -> Channel:
        await ChannelRepository.check_channel_member(self.db, user.id, channel_id)
        channel = await self._get_channel(channel_id)
        if channel.type != ChannelType.GROUP_DM:
            raise ForbiddenException("This channel is not a group DM")
        return channel

    async def _get_channel(self, channel_id: str) -> Channel:
        result = await self.db.execute(select(Channel).where(Channel.id == channel_id))
        channel = result.scalar_one_or_none()
        if not channel:
            raise NotFoundException("Channel not found")
        return channel

    async def _require_friend(self, actor_id: str, user_id: str) -> None:
        if str(actor_id) == str(user_id):
            raise BadRequestException("You cannot add yourself")
        friendship = await FriendshipRepository.get_friendship_by_user_ids(
            self.db, actor_id, user_id
        )
        if not friendship:
            raise ForbiddenException("You can only add your friends to a group")

    async def _reassign_owner_if_needed(
        self, channel_id: str, remaining: list[str]
    ) -> None:
        """Hand the room to the longest-standing member still in it.

        An owner who has left is worse than no owner: the row still names them,
        so a later read attributes the group to someone who cannot see it.
        """
        channel = await self._get_channel(channel_id)
        if channel.owner_id and str(channel.owner_id) in remaining:
            return
        channel.owner_id = remaining[0]
        await self.db.flush()

    async def _delete_channel(self, channel_id: str) -> None:
        await self.db.execute(delete(Message).where(Message.channel_id == channel_id))
        await self.db.execute(
            delete(ChannelMember).where(ChannelMember.channel_id == channel_id)
        )
        await self.db.execute(delete(Channel).where(Channel.id == channel_id))
        await self.db.flush()

    async def _notify_members(
        self,
        *,
        actor: CurrentUser,
        channel_id: str,
        text: str,
        exclude: set[str] | None = None,
    ) -> None:
        """Tell everyone still in the channel that its roster or name moved.

        Published after the transaction, like every other event rest_api sends:
        a Redis outage must not fail a mutation that already committed.
        """
        skip = {str(actor.id)} | (exclude or set())
        member_ids = await ChannelRepository.get_channel_member_ids(self.db, channel_id)
        await realtime_publisher.publish_many(
            events.group_dm_updated(
                actor_id=actor.id,
                to_user_id=member_id,
                channel_id=channel_id,
                text=text,
            )
            for member_id in member_ids
            if member_id not in skip
        )

    async def _username(self, user_id: str) -> str:
        result = await self.db.execute(select(User.username).where(User.id == user_id))
        return result.scalar_one_or_none() or "Someone"


def get_channel_service(db: AsyncSession = Depends(get_db)):
    return ChannelService(db)
