"""Builders for the events rest_api publishes.

Most of these are user-addressed (`receiver_id` is a user id, see
`libs.event.schema.USER_ADDRESSED_EVENT_TYPES`); `voice_state_changed` is the
exception and is addressed to a channel. `sender_id` is whoever caused the
change. Keeping construction here means the metadata contract with the frontend
lives in one file rather than being spelled out at each call site.
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
    from_username: str,
    to_user_id: str,
) -> Event:
    return Event(
        event_type=EventType.NOTIFICATION,
        sender_id=str(from_user_id),
        receiver_id=str(to_user_id),
        text=f"{from_username} invited you to {guild_name}",
        metadata={
            "action": EventAction.GUILD_INVITE_RECEIVED.value,
            "invite_id": str(invite_id),
            "guild_id": str(guild_id),
            "guild_name": guild_name,
            "from_username": from_username,
        },
    )


def guild_invite_removed(
    *,
    invite_id: str,
    guild_id: str,
    guild_name: str,
    user_id: str,
) -> Event:
    """An invite is no longer pending because its recipient declined it.

    Addressed to the recipient rather than the inviter: a user can hold several
    sockets, and the other tabs are still showing the invite they just refused.
    """
    return Event(
        event_type=EventType.NOTIFICATION,
        sender_id=str(user_id),
        receiver_id=str(user_id),
        text=f"You declined the invitation to {guild_name}",
        metadata={
            "action": EventAction.GUILD_INVITE_REMOVED.value,
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


def group_dm_updated(
    *,
    actor_id: str,
    to_user_id: str,
    channel_id: str,
    text: str,
) -> Event:
    """A group DM the recipient is already in changed name or membership.

    Separate from `channels_changed` on purpose. The recipient did not join or
    leave anything, so making the gateway re-read its channel mapping and the
    client rebuild its channel list would be work for a fact neither of them
    got wrong. What is stale is one channel's name and member list, and that is
    what the metadata names.
    """
    return Event(
        event_type=EventType.NOTIFICATION,
        sender_id=str(actor_id),
        receiver_id=str(to_user_id),
        text=text,
        metadata={
            "action": EventAction.GROUP_DM_UPDATED.value,
            "channel_id": str(channel_id),
        },
    )


def guild_updated(
    *,
    actor_id: str,
    to_user_id: str,
    guild_id: str,
    text: str,
) -> Event:
    """A guild the recipient stays in changed name, roster or roles.

    Goes to everyone in the guild, the actor included: the actor's own response
    covers the tab that made the change, and this covers their other tabs. It is
    a refetch, so hearing it twice costs nothing. Someone *leaving* the guild
    gets `channels_changed` instead, because their membership is what changed.
    """
    return Event(
        event_type=EventType.NOTIFICATION,
        sender_id=str(actor_id),
        receiver_id=str(to_user_id),
        text=text,
        metadata={
            "action": EventAction.GUILD_UPDATED.value,
            "guild_id": str(guild_id),
        },
    )


def user_updated(
    *,
    actor_id: str,
    to_user_id: str,
    avatar_url: str | None,
) -> Event:
    """Someone the recipient can see changed their avatar.

    Carries the new URL rather than asking for a refetch: the client's user
    cache only ever fetches ids it has not seen, so without the value in hand
    an old avatar would stay on screen until a reload. Goes to the actor too,
    for their other tabs.
    """
    return Event(
        event_type=EventType.NOTIFICATION,
        sender_id=str(actor_id),
        receiver_id=str(to_user_id),
        text="",
        metadata={
            "action": EventAction.USER_UPDATED.value,
            "user_id": str(actor_id),
            "avatar_url": avatar_url,
        },
    )


def message_edited(
    *, actor_id: str, channel_id: str, message_id: str, text: str, edited_at: str
) -> Event:
    """Channel-addressed, so it reaches who the message reached."""
    return Event(
        event_type=EventType.MESSAGE_UPDATE,
        sender_id=str(actor_id),
        receiver_id=str(channel_id),
        text=text,
        metadata={
            "action": EventAction.MESSAGE_EDITED.value,
            "message_id": str(message_id),
            "edited_at": edited_at,
        },
    )


def message_deleted(*, actor_id: str, channel_id: str, message_id: str) -> Event:
    return Event(
        event_type=EventType.MESSAGE_UPDATE,
        sender_id=str(actor_id),
        receiver_id=str(channel_id),
        text="",
        metadata={
            "action": EventAction.MESSAGE_DELETED.value,
            "message_id": str(message_id),
        },
    )


def voice_state_changed(
    *, actor_id: str, actor_username: str, channel_id: str, joined: bool
) -> Event:
    """Someone joined or left a voice channel.

    Channel-addressed, unlike everything else in this file: it goes to the
    channel's members so their channel list updates, which is the same fan-out
    a chat message gets. This carries presence only — the audio is between the
    client and the SFU.
    """
    action = EventAction.VOICE_JOINED if joined else EventAction.VOICE_LEFT
    verb = "joined" if joined else "left"
    return Event(
        event_type=EventType.VOICE_STATE,
        sender_id=str(actor_id),
        receiver_id=str(channel_id),
        text=f"{actor_username} {verb} voice",
        metadata={
            "action": action.value,
            "channel_id": str(channel_id),
            "user_id": str(actor_id),
            "username": actor_username,
        },
    )
