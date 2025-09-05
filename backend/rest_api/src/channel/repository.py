from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.channel.models import Channel, ChannelMember, ChannelType
from src.channel.schemas import DMChannelCreate
from src.utils.exceptions import NotFoundException


class ChannelRepository:

    @staticmethod
    async def create_dm_channel(
        db: AsyncSession, channel_create: DMChannelCreate
    ) -> Channel:
        new_channel = Channel(
            type=ChannelType.DM,
        )
        db.add(new_channel)
        await db.flush()
        await db.refresh(new_channel)

        channel_member_1 = ChannelMember(
            channel_id=new_channel.id,
            user_id=channel_create.user_id,
        )
        db.add(channel_member_1)
        await db.flush()

        channel_member_2 = ChannelMember(
            channel_id=new_channel.id,
            user_id=channel_create.user_id2,
        )
        db.add(channel_member_2)
        await db.flush()
        return new_channel

    @staticmethod
    async def check_channel_member(
        db: AsyncSession, user_id: str, channel_id: str
    ) -> ChannelMember:
        channel_member = await db.execute(
            select(ChannelMember).where(
                ChannelMember.user_id == user_id, ChannelMember.channel_id == channel_id
            )
        )
        result = channel_member.scalar_one_or_none()
        if not result:
            raise NotFoundException("You are not a member of this channel")
        return result
