from datetime import datetime, timedelta
from enum import Enum

from libs.db.base import Base, generate_id, generate_timestamp
from sqlalchemy import UUID, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey, String
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=generate_timestamp,
        onupdate=generate_timestamp,
    )


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
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: generate_timestamp(timedelta(days=7)),
    )
