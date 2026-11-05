"""Invite links: a URL anyone can use, with no named recipient.

A `GuildInvite` is an offer to one person, so its primary key is
`(guild_id, user_id)`. A link has no such person, which is why it is its own
table rather than a nullable column on that one.

**The code is the credential**: whoever holds it can join. So it is random, long
enough that guessing is not a plan, and the routes that take one are rate limited.

There is no ban list, so someone removed from a guild can come back through any
link they still hold. `GuildMemberStatus.BANNED` exists and nothing reads it.
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends
from libs.db import Guild, GuildInviteLink, GuildMember
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.database.core import get_db
from src.guild.permissions import GuildPermission, allows
from src.guild.repository import GuildRepository
from src.guild.schemas import (
    InviteLinkAccepted,
    InviteLinkCreate,
    InviteLinkPreview,
)
from src.guild.service import GuildService
from src.realtime import events
from src.realtime.publisher import realtime_publisher
from src.utils.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)

# 96 bits, 16 characters. The same answer for a missing, expired and used-up code,
# so that probing cannot tell a dead link from one that never existed.
CODE_BYTES = 12
INVALID_LINK = "This invite is invalid or has expired"
# Keeps one member from filling the table. Expired links do not count.
MAX_LINKS_PER_GUILD = 25


def _usable(now: datetime):
    """The condition for a link that still works, shared by every read of one."""
    return (
        or_(GuildInviteLink.expires_at.is_(None), GuildInviteLink.expires_at > now),
        or_(
            GuildInviteLink.max_uses.is_(None),
            GuildInviteLink.uses < GuildInviteLink.max_uses,
        ),
    )


class InviteLinkService(GuildService):

    async def create_link(
        self, user: CurrentUser, guild_id: str, create: InviteLinkCreate
    ) -> GuildInviteLink:
        async with self.db.begin():
            await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.INVITE
            )
            now = datetime.now(timezone.utc)
            # Dead links have no use and nothing else ever removes them
            await self.db.execute(
                delete(GuildInviteLink).where(
                    GuildInviteLink.guild_id == guild_id,
                    ~(_usable(now)[0] & _usable(now)[1]),
                )
            )
            count = await self.db.execute(
                select(func.count())
                .select_from(GuildInviteLink)
                .where(GuildInviteLink.guild_id == guild_id)
            )
            if count.scalar_one() >= MAX_LINKS_PER_GUILD:
                raise BadRequestException(
                    "This guild has too many invite links. Revoke some first"
                )
            link = GuildInviteLink(
                code=secrets.token_urlsafe(CODE_BYTES),
                guild_id=guild_id,
                creator_id=user.id,
                max_uses=create.max_uses,
                expires_at=(
                    now + timedelta(hours=create.expires_in_hours)
                    if create.expires_in_hours
                    else None
                ),
            )
            self.db.add(link)
            await self.db.flush()
            await self.db.refresh(link)
        return link

    async def list_links(
        self, user: CurrentUser, guild_id: str
    ) -> list[GuildInviteLink]:
        """Admins see every link, anyone else the ones they made."""
        async with self.db.begin():
            standing = await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.INVITE
            )
            query = select(GuildInviteLink).where(
                GuildInviteLink.guild_id == guild_id,
                *_usable(datetime.now(timezone.utc)),
            )
            if not allows(standing, GuildPermission.MANAGE_GUILD):
                query = query.where(GuildInviteLink.creator_id == user.id)
            result = await self.db.execute(
                query.order_by(GuildInviteLink.created_at.desc())
            )
            return list(result.scalars().all())

    async def revoke_link(self, user: CurrentUser, guild_id: str, code: str) -> None:
        async with self.db.begin():
            standing = await GuildRepository.require_permission(
                self.db, guild_id, user.id, GuildPermission.INVITE
            )
            result = await self.db.execute(
                select(GuildInviteLink).where(
                    GuildInviteLink.code == code,
                    GuildInviteLink.guild_id == guild_id,
                )
            )
            link = result.scalar_one_or_none()
            if not link:
                raise NotFoundException("Invite link not found")
            if str(link.creator_id) != str(user.id) and not allows(
                standing, GuildPermission.MANAGE_GUILD
            ):
                raise ForbiddenException("You can only revoke links you made")
            await self.db.delete(link)

    async def preview(self, code: str) -> InviteLinkPreview:
        """What the link is for, shown before signing in. Public, so it says only
        what the person holding the link is being invited to."""
        now = datetime.now(timezone.utc)
        async with self.db.begin():
            result = await self.db.execute(
                select(Guild)
                .join(GuildInviteLink, GuildInviteLink.guild_id == Guild.id)
                .where(GuildInviteLink.code == code, *_usable(now))
            )
            guild = result.scalar_one_or_none()
            if not guild:
                raise NotFoundException(INVALID_LINK)
            members = await self.db.execute(
                select(func.count())
                .select_from(GuildMember)
                .where(GuildMember.guild_id == guild.id)
            )
            return InviteLinkPreview(
                guild_name=guild.name,
                guild_description=guild.description,
                icon_url=guild.icon_url,
                member_count=members.scalar_one(),
            )

    async def accept(self, user: CurrentUser, code: str) -> InviteLinkAccepted:
        now = datetime.now(timezone.utc)
        async with self.db.begin():
            link = await self.db.execute(
                select(GuildInviteLink.guild_id).where(GuildInviteLink.code == code)
            )
            guild_id = link.scalar_one_or_none()
            if not guild_id:
                raise NotFoundException(INVALID_LINK)
            guild_id = str(guild_id)

            # Before the use is counted: following a link into a guild you are
            # already in should take you there, and should not spend a use.
            if await GuildRepository.get_standing(self.db, guild_id, user.id):
                return InviteLinkAccepted(guild_id=guild_id, already_member=True)

            # The check and the increment are one statement. Read-then-write here
            # lets two people through on the last use of a limited link.
            spent = await self.db.execute(
                update(GuildInviteLink)
                .where(GuildInviteLink.code == code, *_usable(now))
                .values(uses=GuildInviteLink.uses + 1)
                .returning(GuildInviteLink.code)
            )
            if spent.first() is None:
                raise NotFoundException(INVALID_LINK)

            await GuildRepository.join_guild(self.db, guild_id, user.id)
            others = await self._member_ids(guild_id, excluding=user.id)

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
        return InviteLinkAccepted(guild_id=guild_id, already_member=False)


def get_invite_link_service(db: AsyncSession = Depends(get_db)):
    return InviteLinkService(db)
