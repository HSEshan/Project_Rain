import logging
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.channel.models import Channel, ChannelMember
from src.database.core import get_db
from src.database.service import BaseService
from src.guild.models import (
    Guild,
    GuildInvite,
    GuildMember,
    GuildMemberRole,
    GuildMemberStatus,
)
from src.guild.repository import GuildRepository
from src.guild.schemas import GuildCreate
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

    async def create_guild_invite(
        self, user: CurrentUser, user_to_invite: str, guild_id: str
    ) -> GuildInvite:
        async with self.db.begin():
            await self.get_guild_by_id(guild_id)
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
            )
            self.db.add(invite)
            await self.db.flush()
            await self.db.refresh(invite)
        return invite

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

            # The invite is single use
            await self.db.delete(result)
        return guild_member

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
