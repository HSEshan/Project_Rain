from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import UUID, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from src.database.core import Base
from src.utils.default import generate_id


class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[str] = mapped_column(
        UUID, primary_key=True, index=True, default=generate_id
    )
    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String, index=True)
    owner_id: Mapped[str] = mapped_column(UUID, index=True)
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class GuildMemberStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BANNED = "banned"


class GuildMember(Base):
    __tablename__ = "guild_members"
    guild_id: Mapped[str] = mapped_column(UUID, index=True, primary_key=True)
    user_id: Mapped[str] = mapped_column(UUID, index=True, primary_key=True)
    status: Mapped[GuildMemberStatus] = mapped_column(
        SQLAlchemyEnum(GuildMemberStatus), index=True
    )
