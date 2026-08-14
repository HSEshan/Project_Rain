"""Builders for the events rest_api publishes.

All of these are user-addressed (`receiver_id` is a user id, see
`libs.event.schema.USER_ADDRESSED_EVENT_TYPES`). `sender_id` is whoever caused
the change. Keeping construction here means the metadata contract with the
frontend lives in one file rather than being spelled out at each call site.
"""

from typing import Optional

from libs.event.schema import (
    CHANNELS_CHANGED_FLAG,
    Event,
    EventAction,
    EventType,
)


def friend_request_received(
    *, request_id: str, from_user_id: str, from_username: str, to_user_id: str
) -> Event:
    return Event(
        event_type=EventType.FRIEND_REQUEST,
        sender_id=str(from_user_id),
        receiver_id=str(to_user_id),
        text=f"{from_username} sent you a friend request",
        metadata={
            "action": EventAction.FRIEND_REQUEST_RECEIVED.value,
            "request_id": str(request_id),
            "from_username": from_username,
        },
    )


def friend_request_accepted(
    *,
    accepted_by_id: str,
    accepted_by_username: str,
    to_user_id: str,
    dm_channel_id: str,
) -> Event:
    """Tells the original sender their request went through, and that they now
    have a DM channel they were not a member of a moment ago."""
    return Event(
        event_type=EventType.NOTIFICATION,
        sender_id=str(accepted_by_id),
        receiver_id=str(to_user_id),
        text=f"{accepted_by_username} accepted your friend request",
        metadata={
            "action": EventAction.FRIEND_REQUEST_ACCEPTED.value,
            CHANNELS_CHANGED_FLAG: True,
            "friend_id": str(accepted_by_id),
            "friend_username": accepted_by_username,
            "dm_channel_id": str(dm_channel_id),
        },
    )


def guild_invite_received(
    *,
    invite_id: str,
    guild_id: str,
    guild_name: str,
    from_user_id: str,
    to_user_id: str,
) -> Event:
    return Event(
        event_type=EventType.NOTIFICATION,
        sender_id=str(from_user_id),
        receiver_id=str(to_user_id),
        text=f"You were invited to {guild_name}",
        metadata={
            "action": EventAction.GUILD_INVITE_RECEIVED.value,
            "invite_id": str(invite_id),
            "guild_id": str(guild_id),
            "guild_name": guild_name,
        },
    )


def channels_changed(
    *,
    actor_id: str,
    to_user_id: str,
    text: str,
    guild_id: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> Event:
    """Membership changed for `to_user_id` — joined a guild, a channel was
    created, or they were removed."""
    metadata = {
        "action": EventAction.CHANNELS_CHANGED.value,
        CHANNELS_CHANGED_FLAG: True,
    }
    if guild_id:
        metadata["guild_id"] = str(guild_id)
    if channel_id:
        metadata["channel_id"] = str(channel_id)

    return Event(
        event_type=EventType.NOTIFICATION,
        sender_id=str(actor_id),
        receiver_id=str(to_user_id),
        text=text,
        metadata=metadata,
    )
