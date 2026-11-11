import logging
from datetime import datetime, timezone

from fastapi import Depends, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from libs.db import (
    CALLABLE_CHANNEL_TYPES,
    Channel,
    ChannelMember,
    Guild,
    GuildBan,
    GuildInvite,
    GuildInviteLink,
    GuildMember,
    GuildMemberRole,
    User,
)
from src.auth.utils import CurrentUser
from src.database.core import get_db
from src.database.service import BaseService
from src.channel.repository import ChannelRepository
from src.guild.permissions import GuildPermission, can_assign, outranks
from src.guild.repository import GuildRepository
from src.guild.schemas import (
    GuildBanResponse,
    GuildCreate,
    GuildInviteSummary,
    GuildUpdate,
)
from src.media.images import ImageKind
from src.media.service import store_image
from src.media.storage import delete_quietly
from src.realtime import events
from src.realtime.publisher import realtime_publisher
from src.voice.room_service import close_rooms, remove_from_rooms
from src.utils.exceptions import (
    AlreadyExistsException,
    BadRequestException,
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

            await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.INVITE
            )
            guild = await self.get_guild_by_id(guild_id)

            existing_member = await self.db.execute(
                select(GuildMember).where(
                    GuildMember.guild_id == guild_id,
                    GuildMember.user_id == user_to_invite,
                )
            )
            if existing_member.scalar_one_or_none():
                raise AlreadyExistsException("User is already a member of this guild")

            if await GuildRepository.is_banned(self.db, guild_id, user_to_invite):
                raise ForbiddenException("That user is banned from this guild")

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

            guild_id = str(result.guild_id)
            # Also consumes the invite, which is single use
            guild_member = await GuildRepository.join_guild(
                self.db, guild_id, user.id
            )
            others = await self._member_ids(guild_id, excluding=user.id)

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
        await self._publish_guild_updated(
            user.id, guild_id, others, f"{user.name} joined"
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
        self, user: CurrentUser, guild_id: str, member_id: str, ban: bool = False
    ) -> bool:
        async with self.db.begin():
            actor = await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.KICK
            )
            target = await GuildRepository.get_standing(self.db, guild_id, member_id)
            if target is None:
                raise NotFoundException("Member not found")
            if not outranks(actor, target):
                raise ForbiddenException(
                    "You can only remove people below you in this guild"
                )

            rooms = await self._voice_rooms(guild_id)
            await self._drop_member(guild_id, member_id)
            if ban:
                self.db.add(
                    GuildBan(guild_id=guild_id, user_id=member_id, banned_by=user.id)
                )
                # An open invite would only fail when accepted
                await self.db.execute(
                    delete(GuildInvite).where(
                        GuildInvite.guild_id == guild_id,
                        GuildInvite.user_id == member_id,
                    )
                )
            remaining = await self._member_ids(guild_id)

        await realtime_publisher.invalidate_user_channels(member_id)
        await realtime_publisher.publish(
            events.channels_changed(
                actor_id=user.id,
                to_user_id=member_id,
                text=f"You were {'banned' if ban else 'removed'} from a guild",
                guild_id=guild_id,
            )
        )
        await self._publish_guild_updated(
            user.id, guild_id, remaining, "A member was removed"
        )
        await remove_from_rooms(rooms, member_id)
        return True

    async def list_bans(
        self, user: CurrentUser, guild_id: str
    ) -> list[GuildBanResponse]:
        async with self.db.begin():
            await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.KICK
            )
            rows = await self.db.execute(
                select(GuildBan.user_id, User.username, GuildBan.created_at)
                .join(User, User.id == GuildBan.user_id)
                .where(GuildBan.guild_id == guild_id)
                .order_by(GuildBan.created_at.desc())
            )
            return [
                GuildBanResponse(
                    user_id=str(user_id), username=username, created_at=created_at
                )
                for user_id, username, created_at in rows.all()
            ]

    async def remove_ban(
        self, user: CurrentUser, guild_id: str, banned_id: str
    ) -> None:
        """Lets them back in by invite. Does not bring them back."""
        async with self.db.begin():
            await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.KICK
            )
            result = await self.db.execute(
                delete(GuildBan)
                .where(GuildBan.guild_id == guild_id, GuildBan.user_id == banned_id)
                .returning(GuildBan.user_id)
            )
            if result.first() is None:
                raise NotFoundException("That user is not banned")

    async def leave_guild(self, user: CurrentUser, guild_id: str) -> None:
        """Leave by your own choice.

        Not `remove_guild_member`, whose rank rule refuses acting on yourself. The
        owner cannot leave: a guild is not left behind with nobody at the top, so
        it has to be given away or deleted first.
        """
        async with self.db.begin():
            standing = await GuildRepository.get_standing(self.db, guild_id, user.id)
            if standing is None:
                raise NotFoundException("You are not a member of this guild")
            if standing.is_owner:
                raise ForbiddenException(
                    "Transfer the guild or delete it before you leave"
                )
            rooms = await self._voice_rooms(guild_id)
            await self._drop_member(guild_id, user.id)
            remaining = await self._member_ids(guild_id)

        await realtime_publisher.invalidate_user_channels(user.id)
        await realtime_publisher.publish(
            events.channels_changed(
                actor_id=user.id,
                to_user_id=user.id,
                text="You left a guild",
                guild_id=guild_id,
            )
        )
        await self._publish_guild_updated(
            user.id, guild_id, remaining, f"{user.name} left"
        )
        await remove_from_rooms(rooms, str(user.id))

    async def transfer_ownership(
        self, user: CurrentUser, guild_id: str, new_owner_id: str
    ) -> Guild:
        async with self.db.begin():
            await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.TRANSFER_OWNERSHIP
            )
            if str(new_owner_id) == str(user.id):
                raise BadRequestException("You already own this guild")
            member = await self.db.execute(
                select(GuildMember).where(
                    GuildMember.guild_id == guild_id,
                    GuildMember.user_id == new_owner_id,
                )
            )
            member = member.scalar_one_or_none()
            if not member:
                raise NotFoundException("Member not found")

            guild = await self.get_guild_by_id(guild_id)
            guild.owner_id = new_owner_id
            # The owner always holds the admin row, see `permissions.py`. The old
            # owner's row already says admin, so they simply stay one.
            member.role = GuildMemberRole.ADMIN
            await self.db.flush()
            await self.db.refresh(guild)
            members = await self._member_ids(guild_id)

        await self._publish_guild_updated(
            user.id, guild_id, members, f"{guild.name} has a new owner"
        )
        return guild

    async def _voice_rooms(self, guild_id: str) -> list[str]:
        """Callers must already hold the transaction. Room id is the channel id."""
        return self._rooms_of(
            await GuildRepository.get_guild_channels(self.db, guild_id)
        )

    @staticmethod
    def _rooms_of(channels: list[Channel]) -> list[str]:
        return [
            str(channel.id)
            for channel in channels
            if channel.type in CALLABLE_CHANNEL_TYPES
        ]

    async def _drop_member(self, guild_id: str, member_id: str) -> None:
        """Callers must already hold the transaction. Leaving a guild leaves every
        channel in it, whoever decided, and ends any link they made: a kick that
        the kicked person can undo with a URL they kept is no kick at all."""
        await self.db.execute(
            delete(GuildInviteLink).where(
                GuildInviteLink.guild_id == guild_id,
                GuildInviteLink.creator_id == member_id,
            )
        )
        await self.db.execute(
            delete(ChannelMember).where(
                ChannelMember.user_id == member_id,
                ChannelMember.channel_id.in_(
                    select(Channel.id).where(Channel.guild_id == guild_id)
                ),
            )
        )
        await self.db.execute(
            delete(GuildMember).where(
                GuildMember.guild_id == guild_id, GuildMember.user_id == member_id
            )
        )

    async def update_guild(
        self, user: CurrentUser, guild_id: str, update: GuildUpdate
    ) -> Guild:
        """Apply only what the body named, see `GuildUpdate`."""
        async with self.db.begin():
            await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.MANAGE_GUILD
            )
            guild = await self.get_guild_by_id(guild_id)
            if "name" in update.model_fields_set:
                guild.name = update.name
            if "description" in update.model_fields_set:
                guild.description = update.description
            await self.db.flush()
            await self.db.refresh(guild)
            members = await self._member_ids(guild_id)

        await self._publish_guild_updated(
            user.id, guild_id, members, f"{guild.name} was updated"
        )
        return guild

    async def delete_guild(self, user: CurrentUser, guild_id: str) -> None:
        """Remove the guild and everything under it.

        Invites and member rows go by cascade. Channels do not: `channels` has
        no cascade from `guilds`, so they are deleted here first, or this fails
        on the foreign key.
        """
        async with self.db.begin():
            await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.DELETE_GUILD
            )
            guild = await self.get_guild_by_id(guild_id)
            name, icon_key = guild.name, guild.icon_key
            members = await self._member_ids(guild_id)
            channels = await GuildRepository.get_guild_channels(self.db, guild_id)
            rooms = self._rooms_of(channels)
            await ChannelRepository.delete_channels(
                self.db, [channel.id for channel in channels]
            )
            await self.db.delete(guild)

        await delete_quietly([icon_key])
        # Membership changed for every one of them, the owner included: their
        # sockets are still mapped to channels that no longer exist.
        await realtime_publisher.invalidate_user_channels(*members)
        await realtime_publisher.publish_many(
            events.channels_changed(
                actor_id=user.id,
                to_user_id=member_id,
                text=f"{name} was deleted",
                guild_id=guild_id,
            )
            for member_id in members
        )
        await close_rooms(rooms)

    async def update_member_role(
        self,
        user: CurrentUser,
        guild_id: str,
        member_id: str,
        role: GuildMemberRole,
    ) -> GuildMember:
        async with self.db.begin():
            actor = await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.MANAGE_ROLES
            )
            target = await GuildRepository.get_standing(self.db, guild_id, member_id)
            if target is None:
                raise NotFoundException("Member not found")
            if not can_assign(actor, target, role):
                raise ForbiddenException(
                    "You can only change the role of people below you in this guild"
                )

            member = await self.db.execute(
                select(GuildMember).where(
                    GuildMember.guild_id == guild_id, GuildMember.user_id == member_id
                )
            )
            member = member.scalar_one()
            member.role = role
            await self.db.flush()
            members = await self._member_ids(guild_id)

        await self._publish_guild_updated(
            user.id, guild_id, members, "A member's role changed"
        )
        return member

    async def _member_ids(
        self, guild_id: str, excluding: str | None = None
    ) -> list[str]:
        """Callers must already hold the transaction."""
        result = await self.db.execute(
            select(GuildMember.user_id).where(GuildMember.guild_id == guild_id)
        )
        return [
            str(member_id)
            for member_id in result.scalars()
            if str(member_id) != str(excluding)
        ]

    async def _publish_guild_updated(
        self, actor_id: str, guild_id: str, member_ids: list[str], text: str
    ) -> None:
        await realtime_publisher.publish_many(
            events.guild_updated(
                actor_id=actor_id,
                to_user_id=member_id,
                guild_id=guild_id,
                text=text,
            )
            for member_id in member_ids
        )

    async def set_icon(
        self, user: CurrentUser, guild_id: str, upload: UploadFile
    ) -> Guild:
        """Replace the icon. Stored first, old object deleted after the commit.

        Checked before the upload is processed, so a non-admin cannot make the
        server decode an image it is only going to refuse to keep.
        """
        async with self.db.begin():
            await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.MANAGE_GUILD
            )
        key, _ = await store_image(upload, ImageKind.ICON, f"guild-icons/{guild_id}")
        return await self._swap_icon(user, guild_id, key)

    async def clear_icon(self, user: CurrentUser, guild_id: str) -> Guild:
        return await self._swap_icon(user, guild_id, None)

    async def _swap_icon(
        self, user: CurrentUser, guild_id: str, key: str | None
    ) -> Guild:
        async with self.db.begin():
            # Checked again inside the transaction that writes: the admin may
            # have been demoted while the image was being processed.
            try:
                await GuildRepository.require_permission(
                    self.db, guild_id, user.id, GuildPermission.MANAGE_GUILD
                )
            except (ForbiddenException, NotFoundException):
                await delete_quietly([key])
                raise
            guild = await self.get_guild_by_id(guild_id)
            old_key, guild.icon_key = guild.icon_key, key
            members = await self._member_ids(guild_id)
        await delete_quietly([old_key])
        # The same refetch a rename triggers. The icon URL changes with every
        # upload (keys are write-once), so a client that re-reads its guilds
        # cannot be served the old picture from cache.
        await self._publish_guild_updated(
            user.id,
            guild_id,
            members,
            "The guild icon changed" if key else "The guild icon was removed",
        )
        return guild

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
