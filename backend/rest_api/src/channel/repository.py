from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from libs.db import Channel, ChannelMember, ChannelType, Message, User
from src.channel.schemas import DMChannelCreate
from src.utils.exceptions import NotFoundException


class ChannelRepository:

    @staticmethod
    async def delete_channels(db: AsyncSession, channel_ids: list[str]) -> None:
        """Drop channels and everything that points at them.

        Order matters: `messages` and `channel_members` both have a foreign key
        to `channels` with no cascade, so they go first. Attachments need
        nothing here: their foreign key sets null, and the media sweep collects
        them like any other unclaimed upload.
        """
        if not channel_ids:
            return
        await db.execute(delete(Message).where(Message.channel_id.in_(channel_ids)))
        await db.execute(
            delete(ChannelMember).where(ChannelMember.channel_id.in_(channel_ids))
        )
        await db.execute(delete(Channel).where(Channel.id.in_(channel_ids)))

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

        await ChannelRepository.add_user_to_channel(
            db, new_channel.id, channel_create.user_id
        )

        await ChannelRepository.add_user_to_channel(
            db, new_channel.id, channel_create.user_id2
        )

        return new_channel

    @staticmethod
    async def add_user_to_channel(
        db: AsyncSession, channel_id: str, user_id: str
    ) -> ChannelMember:
        channel_member = ChannelMember(
            channel_id=channel_id,
            user_id=user_id,
        )
        db.add(channel_member)
        await db.flush()
        await db.refresh(channel_member)
        return channel_member

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

    @staticmethod
    async def remove_user_from_channel(
        db: AsyncSession, channel_id: str, user_id: str
    ) -> None:
        member = await db.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user_id,
            )
        )
        row = member.scalar_one_or_none()
        if row:
            await db.delete(row)
            await db.flush()

    @staticmethod
    async def get_channel_member_ids(db: AsyncSession, channel_id: str) -> list[str]:
        """Everyone in the channel, oldest membership first.

        The order is what decides who inherits a group DM when its owner
        leaves, so it is not incidental.
        """
        members = await db.execute(
            select(ChannelMember.user_id)
            .where(ChannelMember.channel_id == channel_id)
            .order_by(ChannelMember.joined_at)
        )
        return [str(user_id) for user_id in members.scalars().all()]

    @staticmethod
    async def get_channel_members_with_usernames(
        db: AsyncSession, channel_id: str
    ) -> list[tuple[str, str]]:
        """(user_id, username) for each member, oldest membership first."""
        members = await db.execute(
            select(ChannelMember.user_id, User.username)
            .join(User, User.id == ChannelMember.user_id)
            .where(ChannelMember.channel_id == channel_id)
            .order_by(ChannelMember.joined_at)
        )
        return [(str(user_id), username) for user_id, username in members.all()]

    @staticmethod
    async def get_channels_by_guild_ids(
        db: AsyncSession, guild_ids: list[str]
    ) -> list[Channel]:
        channel = await db.execute(
            select(Channel).where(Channel.guild_id.in_(guild_ids))
        )
        result = channel.scalars().all()
        if not result:
            raise NotFoundException("No channels found for these guilds")
        return result

    @staticmethod
    async def get_user_channels(db: AsyncSession, user_id: str) -> list[Channel]:
        channel_members = await db.execute(
            select(ChannelMember.channel_id).where(ChannelMember.user_id == user_id)
        )
        channel_ids = channel_members.scalars().all()
        channels = await db.execute(select(Channel).where(Channel.id.in_(channel_ids)))
        return channels.scalars().all()

    @staticmethod
    async def get_channel_participants(
        db: AsyncSession, current_user_id: str, channel_ids: list[str]
    ) -> dict[str, list[str]]:
        """Who else is in these channels, for the ones the caller is in.

        A channel the caller is not in is left out rather than refused: this is a
        bulk read, and "who is in that DM" is not theirs to learn. It used to
        answer for any channel id at all.
        """
        own_channels = select(ChannelMember.channel_id).where(
            ChannelMember.user_id == current_user_id
        )
        channel_members = await db.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id.in_(channel_ids),
                ChannelMember.channel_id.in_(own_channels),
                ChannelMember.user_id != current_user_id,
            )
        )
        channel_members = channel_members.scalars().all()
        participants = defaultdict(list)
        for channel_member in channel_members:
            participants[channel_member.channel_id].append(channel_member.user_id)
        return participants
