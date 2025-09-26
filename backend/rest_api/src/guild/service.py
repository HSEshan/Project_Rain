import logging
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.channel.models import Channel
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
from src.utils.exceptions import NotFoundException

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

    async def create_guild_invite(
        self, user: CurrentUser, user_to_invite: str, guild_id: str
    ) -> GuildInvite:
        async with self.db.begin():
            guild = await self.get_guild_by_id(guild_id)
            if not guild:
                raise NotFoundException(f"Guild with id {guild_id} not found")

            guild_member = await self.db.execute(
                select(GuildMember).where(
                    GuildMember.guild_id == guild_id, GuildMember.user_id == user.id
                )
            )
            result = guild_member.scalar_one_or_none()
            if not result:
                raise NotFoundException("You are not a member of this guild")

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
                raise NotFoundException("You are not the recipient of this invite")

            guild_member = GuildMember(
                guild_id=result.guild_id,
                user_id=user.id,
                status=GuildMemberStatus.ACTIVE,
                role=GuildMemberRole.MEMBER,
            )
            self.db.add(guild_member)
            await self.db.flush()
            await self.db.refresh(guild_member)
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
                raise NotFoundException("You are not an admin of this guild")

            guild_member = await self.db.execute(
                select(GuildMember).where(
                    GuildMember.guild_id == guild_id, GuildMember.user_id == member_id
                )
            )
            result = guild_member.scalar_one_or_none()
            if not result:
                raise NotFoundException("Member not found")

            self.db.delete(result)
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
