from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.channel.models import Channel, ChannelType
from src.channel.repository import ChannelRepository
from src.guild.models import Guild, GuildMember, GuildMemberRole, GuildMemberStatus
from src.guild.schemas import GuildChannelCreate, GuildCreate


class GuildRepository:
    @staticmethod
    async def create_guild(
        db: AsyncSession, guild: GuildCreate, user: CurrentUser
    ) -> Guild:
        new_guild = Guild(
            name=guild.name,
            description=guild.description,
            owner_id=user.id,
        )
        db.add(new_guild)
        await db.flush()
        await db.refresh(new_guild)
        await GuildRepository.add_guild_member(
            db, new_guild.id, user.id, GuildMemberRole.ADMIN
        )
        channel_text = await GuildRepository.create_guild_channel(
            db,
            new_guild.id,
            GuildChannelCreate(name="general-text", type=ChannelType.GUILD_TEXT),
        )
        channel_voice = await GuildRepository.create_guild_channel(
            db,
            new_guild.id,
            GuildChannelCreate(name="general-voice", type=ChannelType.GUILD_VOICE),
        )
        await ChannelRepository.add_user_to_channel(db, channel_text.id, user.id)
        await ChannelRepository.add_user_to_channel(db, channel_voice.id, user.id)
        return new_guild

    @staticmethod
    async def add_guild_member(
        db: AsyncSession, guild_id: str, user_id: str, role: GuildMemberRole
    ) -> GuildMember:
        guild_member = GuildMember(
            guild_id=guild_id,
            user_id=user_id,
            role=role,
            status=GuildMemberStatus.ACTIVE,
        )
        db.add(guild_member)
        await db.flush()
        await db.refresh(guild_member)
        return guild_member

    @staticmethod
    async def create_guild_channel(
        db: AsyncSession, guild_id: str, channel_create: GuildChannelCreate
    ) -> Channel:
        new_channel = Channel(
            name=channel_create.name,
            type=channel_create.type,
            guild_id=guild_id,
            description=channel_create.description,
        )
        db.add(new_channel)
        await db.flush()
        await db.refresh(new_channel)
        return new_channel

    @staticmethod
    async def get_user_guilds(db: AsyncSession, user_id: str) -> list[Guild]:
        guilds = await db.execute(
            select(Guild).where(
                Guild.id.in_(
                    select(GuildMember.guild_id).where(GuildMember.user_id == user_id)
                )
            )
        )
        return guilds.scalars().all()

    @staticmethod
    async def get_guild_channels(db: AsyncSession, guild_id: str) -> list[Channel]:
        channels = await db.execute(select(Channel).where(Channel.guild_id == guild_id))
        return channels.scalars().all()
