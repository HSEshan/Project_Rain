from datetime import datetime
from enum import Enum
from typing import Optional

from libs.db.base import Base, generate_id, generate_timestamp
from sqlalchemy import UUID, DateTime
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column


class ChannelType(Enum):
    DM = "dm"
    # A DM with more than two people in it. Same messages, same events, same
    # voice: what it adds is a mutable member list, a name, and an owner. Kept
    # as its own type rather than "a DM that happens to have three members" so
    # that authorisation can be read off the row, not counted.
    GROUP_DM = "group_dm"
    GUILD_TEXT = "guild_text"
    GUILD_VOICE = "guild_voice"


# Channels whose members can call each other. Guild voice channels are the
# original case; DMs and group DMs joined them in 2026-08-25. Guild *text*
# channels are the exclusion, and the reason this is a set rather than a
# not-equal check.
CALLABLE_CHANNEL_TYPES = frozenset(
    {ChannelType.GUILD_VOICE, ChannelType.DM, ChannelType.GROUP_DM}
)

# Channels that are private conversations rather than part of a guild.
DIRECT_CHANNEL_TYPES = frozenset({ChannelType.DM, ChannelType.GROUP_DM})

# Discord's number, and a real constraint rather than a stylistic one: a group
# DM has no roles, no moderation and no invite flow, so it stops being usable
# well before it stops being possible.
MAX_GROUP_DM_MEMBERS = 10


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
    # Group DMs only. Null for every other type: a guild channel's owner is the
    # guild's, and a two-person DM has no asymmetry to record. It moves to the
    # longest-standing remaining member when the owner leaves, so it never
    # points at someone who is no longer in the channel.
    owner_id: Mapped[Optional[str]] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
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
    # When they joined. Added for group DMs, where it gives "longest-standing
    # member" a meaning: that is who inherits the channel when the owner
    # leaves. A server default so the rows that predate this column get one.
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp, server_default=func.now()
    )
