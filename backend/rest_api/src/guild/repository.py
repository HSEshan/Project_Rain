from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from libs.db import Channel, ChannelType
from src.channel.repository import ChannelRepository
from src.channel.schemas import GuildChannelCreate
from libs.db import (
    ChannelMember,
    Guild,
    GuildBan,
    GuildInvite,
    GuildMember,
    GuildMemberRole,
    GuildMemberStatus,
)
from src.guild.permissions import DENIED, GuildPermission, Standing, allows
from src.guild.schemas import GuildCreate
from src.utils.exceptions import ForbiddenException, NotFoundException


class GuildRepository:
    @staticmethod
    async def get_standing(
        db: AsyncSession, guild_id: str, user_id: str
    ) -> Standing | None:
        """This user's standing in this guild, or None if they are not in it."""
        result = await db.execute(
            select(GuildMember.role, Guild.owner_id)
            .join(Guild, Guild.id == GuildMember.guild_id)
            .where(GuildMember.guild_id == guild_id, GuildMember.user_id == user_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        role, owner_id = row
        return Standing(role=role, is_owner=str(owner_id) == str(user_id))

    @staticmethod
    async def require_permission(
        db: AsyncSession, guild_id: str, user_id: str, permission: GuildPermission
    ) -> Standing:
        """Raises unless this user may do this. Every guild check comes here.

        404 for a non-member, 403 for a member without the permission: whether
        a guild exists is itself only for its members to know.
        """
        standing = await GuildRepository.get_standing(db, guild_id, user_id)
        if standing is None:
            raise NotFoundException("You are not a member of this guild")
        if not allows(standing, permission):
            raise ForbiddenException(DENIED[permission])
        return standing

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
    async def is_banned(db: AsyncSession, guild_id: str, user_id: str) -> bool:
        result = await db.execute(
            select(GuildBan.user_id).where(
                GuildBan.guild_id == guild_id, GuildBan.user_id == user_id
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def join_guild(db: AsyncSession, guild_id: str, user_id: str) -> GuildMember:
        """Make someone a member, by whichever kind of invite got them here.

        Joining a guild joins every channel that already exists in it, and uses up
        any invite they were holding: it could only fail if accepted now.

        The ban check is here because this is the one way in, so no kind of invite
        added later can forget it.
        """
        if await GuildRepository.is_banned(db, guild_id, user_id):
            raise ForbiddenException("You are banned from this guild")
        member = await GuildRepository.add_guild_member(
            db, guild_id, user_id, GuildMemberRole.MEMBER
        )
        channels = await GuildRepository.get_guild_channels(db, guild_id)
        db.add_all(
            [
                ChannelMember(channel_id=channel.id, user_id=user_id)
                for channel in channels
            ]
        )
        await db.execute(
            delete(GuildInvite).where(
                GuildInvite.guild_id == guild_id, GuildInvite.user_id == user_id
            )
        )
        await db.flush()
        return member

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
