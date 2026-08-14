import logging
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from libs.db import (
    Channel,
    ChannelMember,
    Guild,
    GuildInvite,
    GuildMember,
    GuildMemberRole,
    GuildMemberStatus,
    User,
)
from src.auth.utils import CurrentUser
from src.database.core import get_db
from src.database.service import BaseService
from src.guild.repository import GuildRepository
from src.guild.schemas import GuildCreate, GuildInviteSummary
from src.realtime import events
from src.realtime.publisher import realtime_publisher
from src.utils.exceptions import (
    AlreadyExistsException,
    ForbiddenException,
    NotFoundException,
)

logger = logging.getLogger(__name__)


class GuildService(BaseService):

    async def create_guild(self, user: CurrentUser, guild: GuildCreate) -> Guild:
        async with self.db.begin():
            new_guild = await GuildRepository.create_guild(self.db, guild, user)
            guild_id = str(new_guild.id)

        # Creating a guild also makes the creator a member of `general-text`
        # and `general-voice`. Their socket connected before those channels
        # existed, so the gateway has no mapping for them and nothing is
        # registered against `channel:{id}:grpc_endpoints` — a message sent to
        # the new channel would be persisted and then dropped on the way back
        # out. This is the same seam guild *join* has always used.
        await realtime_publisher.invalidate_user_channels(user.id)
        await realtime_publisher.publish(
            events.channels_changed(
                actor_id=user.id,
                to_user_id=user.id,
                text=f"Created {new_guild.name}",
                guild_id=guild_id,
            )
        )
        return new_guild

    async def get_user_guilds(self, user: CurrentUser) -> list[Guild]:
        user_guilds = await GuildRepository.get_user_guilds(self.db, user.id)
        return user_guilds

    async def get_guild_by_id(self, guild_id: str) -> Guild:
        guild = await self.db.execute(select(Guild).where(Guild.id == guild_id))
        result = guild.scalar_one_or_none()
        if not result:
            raise NotFoundException(f"Guild with id {guild_id} not found")
        return result

    async def get_guild_for_user(self, user: CurrentUser, guild_id: str) -> Guild:
        await self.check_guild_member(user.id, guild_id)
        return await self.get_guild_by_id(guild_id)

    async def check_guild_member(self, user_id: str, guild_id: str) -> GuildMember:
        guild_member = await self.db.execute(
            select(GuildMember).where(
                GuildMember.guild_id == guild_id, GuildMember.user_id == user_id
            )
        )
        result = guild_member.scalar_one_or_none()
        if not result:
            raise NotFoundException("You are not a member of this guild")
        return result

    async def get_user_guild_invites(
        self, user: CurrentUser
    ) -> list[GuildInviteSummary]:
        """Invites waiting for this user.

        Without this the only way to learn about an invite is the realtime
        event, which a reload throws away — an invite sent while you were
        offline would never be seen.
        """
        # Outer join on the inviter: the column is nullable, and an inner join
        # would silently hide every invite that predates it.
        inviter = aliased(User)
        result = await self.db.execute(
            select(
                GuildInvite.invite_id,
                GuildInvite.guild_id,
                Guild.name,
                GuildInvite.inviter_id,
                inviter.username,
                GuildInvite.expires_at,
            )
            .join(Guild, Guild.id == GuildInvite.guild_id)
            .outerjoin(inviter, inviter.id == GuildInvite.inviter_id)
            .where(
                GuildInvite.user_id == user.id,
                GuildInvite.expires_at > datetime.now(timezone.utc),
            )
        )
        return [
            GuildInviteSummary(
                invite_id=str(invite_id),
                guild_id=str(guild_id),
                guild_name=guild_name,
                inviter_id=str(inviter_id) if inviter_id else None,
                inviter_username=inviter_username,
                expires_at=expires_at,
            )
            for (
                invite_id,
                guild_id,
                guild_name,
                inviter_id,
                inviter_username,
                expires_at,
            ) in result.all()
        ]

    async def create_guild_invite(
        self,
        user: CurrentUser,
        guild_id: str,
        user_to_invite: str | None = None,
        username: str | None = None,
    ) -> GuildInvite:
        async with self.db.begin():
            # Inside the block, not before it: `AsyncSession` autobegins, so an
            # earlier query makes `begin()` raise (see AGENTS.md)
            if username:
                user_to_invite = await self._user_id_for_username(username)
            if str(user_to_invite) == str(user.id):
                raise AlreadyExistsException("You are already a member of this guild")

            guild = await self.get_guild_by_id(guild_id)
            await self.check_guild_member(user.id, guild_id)

            existing_member = await self.db.execute(
                select(GuildMember).where(
                    GuildMember.guild_id == guild_id,
                    GuildMember.user_id == user_to_invite,
                )
            )
            if existing_member.scalar_one_or_none():
                raise AlreadyExistsException("User is already a member of this guild")

            # (guild_id, user_id) is the invite primary key — one open invite per user
            existing_invite = await self.db.execute(
                select(GuildInvite).where(
                    GuildInvite.guild_id == guild_id,
                    GuildInvite.user_id == user_to_invite,
                )
            )
            if existing_invite.scalar_one_or_none():
                raise AlreadyExistsException("User already has an invite to this guild")

            invite = GuildInvite(
                guild_id=guild_id,
                user_id=user_to_invite,
                inviter_id=user.id,
            )
            self.db.add(invite)
            await self.db.flush()
            await self.db.refresh(invite)
            guild_name = guild.name

        await realtime_publisher.publish(
            events.guild_invite_received(
                invite_id=invite.invite_id,
                guild_id=guild_id,
                guild_name=guild_name,
                from_user_id=user.id,
                from_username=user.name,
                to_user_id=user_to_invite,
            )
        )
        return invite

    async def _user_id_for_username(self, username: str) -> str:
        """Callers must already hold the transaction — see `create_guild_invite`."""
        result = await self.db.execute(
            select(User.id).where(User.username == username)
        )
        user_id = result.scalar_one_or_none()
        if not user_id:
            raise NotFoundException(f"No user named {username}")
        return str(user_id)

    async def accept_guild_invite(
        self, user: CurrentUser, invite_id: str
    ) -> GuildMember:
        async with self.db.begin():

            invite = await self.db.execute(
                select(GuildInvite).where(GuildInvite.invite_id == invite_id)
            )
            result = invite.scalar_one_or_none()
            if not result:
                raise NotFoundException("Invite not found")

            if result.expires_at < datetime.now(timezone.utc):
                raise NotFoundException("Invite has expired")

            if str(result.user_id) != str(user.id):
                logger.info(f"result.user_id: {result.user_id}, user.id: {user.id}")
                raise ForbiddenException("You are not the recipient of this invite")

            existing_member = await self.db.execute(
                select(GuildMember).where(
                    GuildMember.guild_id == result.guild_id,
                    GuildMember.user_id == user.id,
                )
            )
            if existing_member.scalar_one_or_none():
                raise AlreadyExistsException("You are already a member of this guild")

            guild_member = GuildMember(
                guild_id=result.guild_id,
                user_id=user.id,
                status=GuildMemberStatus.ACTIVE,
                role=GuildMemberRole.MEMBER,
            )
            self.db.add(guild_member)
            await self.db.flush()
            await self.db.refresh(guild_member)

            # Joining a guild joins every channel that already exists in it
            guild_channels = await GuildRepository.get_guild_channels(
                self.db, result.guild_id
            )
            self.db.add_all(
                [
                    ChannelMember(channel_id=channel.id, user_id=user.id)
                    for channel in guild_channels
                ]
            )
            await self.db.flush()

            guild_id = str(result.guild_id)
            # The invite is single use
            await self.db.delete(result)

        # The joiner is now a member of every channel in the guild
        await realtime_publisher.invalidate_user_channels(user.id)
        await realtime_publisher.publish(
            events.channels_changed(
                actor_id=user.id,
                to_user_id=user.id,
                text="You joined a guild",
                guild_id=guild_id,
            )
        )
        return guild_member

    async def decline_guild_invite(self, user: CurrentUser, invite_id: str) -> bool:
        """Refuse an invite.

        Deliberately allowed for an expired invite too: the recipient's list is
        filtered by expiry, but a row they can see and cannot dismiss would be
        the worse outcome if the two ever disagree.
        """
        async with self.db.begin():
            invite = await self.db.execute(
                select(GuildInvite).where(GuildInvite.invite_id == invite_id)
            )
            result = invite.scalar_one_or_none()
            if not result:
                raise NotFoundException("Invite not found")

            if str(result.user_id) != str(user.id):
                raise ForbiddenException("You are not the recipient of this invite")

            guild = await self.get_guild_by_id(result.guild_id)
            guild_id, guild_name = str(result.guild_id), guild.name
            await self.db.delete(result)

        # Nothing about membership changed, so no `channels_changed` here — this
        # only tells the user's other sockets to drop the row from their list.
        await realtime_publisher.publish(
            events.guild_invite_removed(
                invite_id=invite_id,
                guild_id=guild_id,
                guild_name=guild_name,
                user_id=user.id,
            )
        )
        return True

    async def remove_guild_member(
        self, user: CurrentUser, guild_id: str, member_id: str
    ) -> bool:
        async with self.db.begin():
            admin_member = await self.db.execute(
                select(GuildMember).where(
                    GuildMember.guild_id == guild_id, GuildMember.user_id == user.id
                )
            )
            result = admin_member.scalar_one_or_none()
            if not result or result.role != GuildMemberRole.ADMIN:
                raise ForbiddenException("You are not an admin of this guild")

            guild_member = await self.db.execute(
                select(GuildMember).where(
                    GuildMember.guild_id == guild_id, GuildMember.user_id == member_id
                )
            )
            result = guild_member.scalar_one_or_none()
            if not result:
                raise NotFoundException("Member not found")

            # Leaving the guild leaves every channel in it
            await self.db.execute(
                delete(ChannelMember).where(
                    ChannelMember.user_id == member_id,
                    ChannelMember.channel_id.in_(
                        select(Channel.id).where(Channel.guild_id == guild_id)
                    ),
                )
            )
            await self.db.delete(result)
            await self.db.flush()

        await realtime_publisher.invalidate_user_channels(member_id)
        await realtime_publisher.publish(
            events.channels_changed(
                actor_id=user.id,
                to_user_id=member_id,
                text="You were removed from a guild",
                guild_id=guild_id,
            )
        )
        return True

    async def get_guild_members(self, guild_id: str) -> list[GuildMember]:
        guild_members = await self.db.execute(
            select(GuildMember).where(GuildMember.guild_id == guild_id)
        )
        return guild_members.scalars().all()

    async def get_guild_channels(self, guild_id: str) -> list[Channel]:
        guild_channels = await GuildRepository.get_guild_channels(self.db, guild_id)
        return guild_channels


def get_guild_service(db: AsyncSession = Depends(get_db)):
    return GuildService(db)
