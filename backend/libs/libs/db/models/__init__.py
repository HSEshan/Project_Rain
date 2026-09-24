"""Every ORM model, imported for its side effect of registering on `Base`.

Alembic autogenerate and any `create_all` only see tables that have been
imported, so nothing here may be dropped even if it looks unused.
"""

from libs.db.models.channel import (
    CALLABLE_CHANNEL_TYPES,
    DIRECT_CHANNEL_TYPES,
    MAX_GROUP_DM_MEMBERS,
    Channel,
    ChannelMember,
    ChannelType,
)
from libs.db.models.friendship import FriendRequest, Friendship
from libs.db.models.guild import (
    Guild,
    GuildInvite,
    GuildMember,
    GuildMemberRole,
    GuildMemberStatus,
)
from libs.db.models.message import Message
from libs.db.models.session import RefreshToken
from libs.db.models.user import BIO_MAX_LENGTH, User

__all__ = [
    "BIO_MAX_LENGTH",
    "CALLABLE_CHANNEL_TYPES",
    "DIRECT_CHANNEL_TYPES",
    "MAX_GROUP_DM_MEMBERS",
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
    "RefreshToken",
    "User",
]
