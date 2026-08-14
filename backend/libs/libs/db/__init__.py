"""Shared SQLAlchemy layer.

`rest_api` and `ws_gateway` both talk to the same Postgres database. Before
this package they each carried their own copy of `Channel`, `User` and
`Message`, which drifted (one used `datetime.now(timezone.utc)` evaluated at
import time as a column default). There is now one definition.

Importing `libs.db` requires the `db` extra (`pip install libs[db]`);
`event_consumer` and `lease_manager` must not use it — they have no Postgres
dependency by design.
"""

from libs.db.base import (
    Base,
    generate_id,
    generate_timestamp,
    generate_timestamp_iso,
)
from libs.db.models import (
    Channel,
    ChannelMember,
    ChannelType,
    FriendRequest,
    Friendship,
    Guild,
    GuildInvite,
    GuildMember,
    GuildMemberRole,
    GuildMemberStatus,
    Message,
    User,
)
from libs.db.session import create_engine, create_session_factory

__all__ = [
    "Base",
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
    "create_engine",
    "create_session_factory",
    "generate_id",
    "generate_timestamp",
    "generate_timestamp_iso",
]
