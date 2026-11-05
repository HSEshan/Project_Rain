from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from libs.db.base import Base, generate_id, generate_timestamp
from libs.media import media_url
from sqlalchemy import UUID, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column


class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[str] = mapped_column(
        UUID, primary_key=True, index=True, default=generate_id
    )
    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String, index=True)
    owner_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Storage key, like `User.avatar_key`. Null is the common case: the letter
    # avatar is what most guilds will ever show.
    icon_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=generate_timestamp,
        onupdate=generate_timestamp,
    )

    @property
    def icon_url(self) -> Optional[str]:
        return media_url(self.icon_key)


class GuildMemberStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"


class GuildMemberRole(Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    MEMBER = "member"


class GuildMember(Base):
    __tablename__ = "guild_members"

    guild_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("guilds.id", ondelete="CASCADE"), index=True, primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, primary_key=True
    )
    status: Mapped[GuildMemberStatus] = mapped_column(
        SQLAlchemyEnum(GuildMemberStatus), index=True
    )
    role: Mapped[GuildMemberRole] = mapped_column(
        SQLAlchemyEnum(GuildMemberRole), index=True, default=GuildMemberRole.MEMBER
    )


class GuildInvite(Base):
    __tablename__ = "guild_invites"

    invite_id: Mapped[str] = mapped_column(UUID, index=True, default=generate_id)
    guild_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("guilds.id", ondelete="CASCADE"), index=True, primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, primary_key=True
    )
    # Who sent it, so the recipient can see more than a guild name. Nullable
    # because invites predating this column have no answer, and because the
    # inviter may later delete their account — the invite is still valid.
    inviter_id: Mapped[Optional[str]] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: generate_timestamp(timedelta(days=7)),
    )


class GuildInviteLink(Base):
    """A shareable URL with no named recipient, unlike `GuildInvite`.

    `max_uses` and `expires_at` are both optional: a link with neither is the
    standing front door of a public guild.
    """

    __tablename__ = "guild_invite_links"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    guild_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("guilds.id", ondelete="CASCADE"), index=True
    )
    # Nullable for the reason `GuildInvite.inviter_id` is: a link outlives its
    # creator's account.
    creator_id: Mapped[Optional[str]] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp
    )


class GuildBan(Base):
    """Someone who may not come back.

    A table rather than `GuildMemberStatus.BANNED` on the member row, which would
    leave a banned user in `guild_members` and make every query of that table one
    forgotten filter away from treating them as a member.
    """

    __tablename__ = "guild_bans"

    guild_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("guilds.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    banned_by: Mapped[Optional[str]] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp
    )
