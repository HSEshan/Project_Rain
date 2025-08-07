from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.database.core import get_db
from src.database.service import BaseService
from src.guild.models import (
    Guild,
    GuildInvite,
    GuildMember,
    GuildMemberRole,
    GuildMemberStatus,
)
from src.guild.schemas import GuildCreate
from src.utils.exceptions import NotFoundException


class GuildService(BaseService):

    async def create_guild(self, user: CurrentUser, guild: GuildCreate) -> Guild:
        async with self.db.begin():
            new_guild = Guild(
                name=guild.name,
                description=guild.description,
                owner_id=user.id,
            )
            self.db.add(new_guild)
            await self.db.flush()
            await self.db.refresh(new_guild)

            guild_member = GuildMember(
                guild_id=new_guild.id,
                user_id=user.id,
                status=GuildMemberStatus.ACTIVE,
                role=GuildMemberRole.ADMIN,
            )

            self.db.add(guild_member)
            await self.db.flush()
            await self.db.refresh(guild_member)

        return new_guild

    async def create_guild_invite(
        self, user: CurrentUser, to_invite: str, guild_id: str
    ) -> GuildInvite:
        async with self.db.begin():
            guild = await self.db.get(Guild, guild_id)
            if not guild:
                raise NotFoundException("Guild not found")

            guild_member = await self.db.get(
                GuildMember, guild_id=guild_id, user_id=user.id
            )
            if not guild_member:
                raise NotFoundException("You are not a member of this guild")

            invite = GuildInvite(
                guild_id=guild_id,
                user_id=to_invite,
            )
            self.db.add(invite)
            await self.db.flush()
            await self.db.refresh(invite)
        return invite

    async def accept_guild_invite(
        self, user: CurrentUser, invite_id: str
    ) -> GuildMember:
        async with self.db.begin():

            invite = await self.db.get(GuildInvite, invite_id)
            if not invite:
                raise NotFoundException("Invite not found")

            if invite.expires_at < datetime.now(timezone.utc):
                raise NotFoundException("Invite has expired")

            if invite.user_id != user.id:
                raise NotFoundException("You are not the recipient of this invite")

            guild_member = GuildMember(
                guild_id=invite.guild_id,
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
            admin_member = await self.db.get(
                GuildMember,
                guild_id=guild_id,
                user_id=user.id,
            )
            if not admin_member or admin_member.role != GuildMemberRole.ADMIN:
                raise NotFoundException("You are not an admin of this guild")

            guild_member = await self.db.get(
                GuildMember, guild_id=guild_id, user_id=member_id
            )
            if not guild_member:
                raise NotFoundException("Member not found")

            self.db.delete(guild_member)
            await self.db.flush()
        return True


def get_guild_service(db: AsyncSession = Depends(get_db)):
    return GuildService(db)
