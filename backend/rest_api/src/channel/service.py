from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from src.auth.utils import CurrentUser
from src.channel.models import Channel, ChannelMember, ChannelType
from src.channel.repository import ChannelRepository
from src.channel.schemas import DMChannelCreate, DMChannelResponse, GuildChannelCreate
from src.database.core import get_db
from src.database.service import BaseService
from src.guild.models import GuildMember, GuildMemberRole
from src.user.models import User
from src.utils.exceptions import NotFoundException


class ChannelService(BaseService):
    async def create_dm_channel(self, channel_create: DMChannelCreate) -> Channel:
        async with self.db.begin():
            new_channel = await ChannelRepository.create_dm_channel(
                self.db, channel_create
            )

        return new_channel

    async def create_guild_channel(
        self, user: CurrentUser, guild_id: str, channel_create: GuildChannelCreate
    ) -> Channel:
        # Check if user is admin of the guild
        guild_member = await self.db.execute(
            select(GuildMember).where(
                GuildMember.guild_id == guild_id, GuildMember.user_id == user.id
            )
        )
        result = guild_member.scalar_one_or_none()
        if not result or result.role != GuildMemberRole.ADMIN:
            raise NotFoundException("You are not an admin of this guild")

        async with self.db.begin():
            new_channel = Channel(
                name=channel_create.name,
                type=channel_create.type,
                guild_id=guild_id,
                description=channel_create.description,
            )
            self.db.add(new_channel)
            await self.db.flush()
            await self.db.refresh(new_channel)

            guild_member_ids = await self.db.execute(
                select(GuildMember.user_id).where(GuildMember.guild_id == guild_id)
            )
            self.db.add_all(
                [
                    ChannelMember(channel_id=new_channel.id, user_id=member_id)
                    for member_id in guild_member_ids.scalars().all()
                ]
            )
            await self.db.flush()
            await self.db.refresh(new_channel)
        return new_channel

    async def get_channel_by_id(self, channel_id: str) -> Channel:
        channel = await self.db.execute(select(Channel).where(Channel.id == channel_id))
        result = channel.scalar_one_or_none()
        if not result:
            raise NotFoundException("Channel not found")
        return result

    async def get_user_dm_channels(self, user: CurrentUser) -> list[dict]:
        OtherUser = aliased(User)

        stmt = (
            select(Channel.id, OtherUser.id, OtherUser.username)
            .join(ChannelMember, ChannelMember.channel_id == Channel.id)
            .join(OtherUser, OtherUser.id == ChannelMember.user_id)
            .where(
                Channel.type == ChannelType.DM,
                Channel.id.in_(
                    select(ChannelMember.channel_id).where(
                        ChannelMember.user_id == user.id
                    )
                ),
                OtherUser.id != user.id,  # exclude self
            )
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        response = DMChannelResponse()
        for channel_id, other_id, other_username in rows:
            response.push(channel_id, {"id": other_id, "username": other_username})

        return response.to_list()


def get_channel_service(db: AsyncSession = Depends(get_db)):
    return ChannelService(db)
