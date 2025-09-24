from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import UUID, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from src.database.core import Base
from src.utils.default import generate_id, generate_timestamp


class ChannelType(Enum):
    DM = "dm"
    GUILD_TEXT = "guild_text"
    GUILD_VOICE = "guild_voice"


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(
        UUID, primary_key=True, index=True, default=generate_id
    )
    name: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    type: Mapped[ChannelType] = mapped_column(SQLAlchemyEnum(ChannelType), index=True)
    guild_id: Mapped[Optional[str]] = mapped_column(
        UUID, ForeignKey("guilds.id"), index=True, nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp
    )


class ChannelMember(Base):
    __tablename__ = "channel_members"

    id: Mapped[str] = mapped_column(
        UUID, primary_key=True, index=True, default=generate_id
    )
    channel_id: Mapped[str] = mapped_column(UUID, ForeignKey("channels.id"), index=True)
    user_id: Mapped[str] = mapped_column(UUID, ForeignKey("users.id"), index=True)
