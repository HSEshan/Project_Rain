"""Every ORM model, imported for its side effect of registering on `Base`.

Alembic autogenerate and any `create_all` only see tables that have been
imported, so nothing here may be dropped even if it looks unused.
"""

from libs.db.models.channel import Channel, ChannelMember, ChannelType
from libs.db.models.friendship import FriendRequest, Friendship
from libs.db.models.guild import (
    Guild,
    GuildInvite,
    GuildMember,
    GuildMemberRole,
    GuildMemberStatus,
)
from libs.db.models.message import Message
from libs.db.models.user import User

__all__ = [
    "Channel",
    "ChannelMember",
    "ChannelType",
    "FriendRequest",
    "Friendship",
    "Guild",
    "GuildInvite",
    "GuildMember",
    "GuildMemberRole",
    "GuildMemberStatus",
    "Message",
    "User",
]
