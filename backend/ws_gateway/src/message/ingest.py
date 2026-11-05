"""What a client is allowed to say over the socket.

**A client may send one thing: a message, to a channel.** Everything else that
travels on this pipeline (notifications, friend requests, voice presence) is
produced by rest_api, and until 2026-11-04 the socket would happily take any of
them from anyone: `Event(**json)` went straight onto the stream, so a user could
hand any other user a forged notification, or write into a conversation they had
never been part of.

So a frame is not filtered, it is **rebuilt**. Only three things are read out of
it and the event is constructed from those, which means `event_id`, `timestamp`,
`target_type` and anything added to `Event` later are the server's by default
rather than the client's until someone remembers to strip them. That matters
beyond forgery: one batch is one transaction, so a single event that fails its
insert (a duplicate `event_id`, a channel id that is not a uuid) used to roll back
every other person's message in that batch, and they were never seen again.

This checks what the frame *is*. Whether the sender may post in that channel needs
Postgres and is decided per batch, see `MessageEventDispatcher.authorized`.
"""

from typing import Any
from uuid import UUID

from libs.db import MAX_ATTACHMENTS_PER_MESSAGE, MAX_MESSAGE_LENGTH
from libs.event.schema import (
    Event,
    EventAction,
    EventType,
    TargetType,
)
from libs.rate_limit import RateLimit
from src.message.dispatcher import ATTACHMENT_IDS_KEY

# A person typing does not reach this. Someone pasting a list of lines one at a
# time might, and a script certainly does.
MESSAGE_RATE = RateLimit("ws:message", 20, 10)


def build_client_event(frame: Any, sender_id: str) -> Event | None:
    """The event a client's frame may become, or None to drop it."""
    if not isinstance(frame, dict) or frame.get("event_type") != EventType.MESSAGE.value:
        return None

    channel_id = _uuid(frame.get("target_id") or frame.get("receiver_id"))
    text = frame.get("text", "")
    if channel_id is None or not isinstance(text, str):
        return None

    # A NUL cannot be stored in a Postgres text column, and a lone surrogate
    # cannot be encoded on the way there. Either would fail the shared batch.
    text = text.replace("\x00", "")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if len(text) > MAX_MESSAGE_LENGTH:
        return None

    metadata = frame.get("metadata")
    requested = metadata.get(ATTACHMENT_IDS_KEY) if isinstance(metadata, dict) else None
    attachment_ids = _valid_ids(requested)[:MAX_ATTACHMENTS_PER_MESSAGE]

    # A message needs text or at least one image. Whitespace alone is nothing,
    # and would persist a row that renders as an empty bubble.
    if not text.strip() and not attachment_ids:
        return None

    return Event(
        event_type=EventType.MESSAGE,
        sender_id=sender_id,
        target_type=TargetType.CHANNEL,
        target_id=channel_id,
        text=text,
        metadata={ATTACHMENT_IDS_KEY: attachment_ids} if attachment_ids else None,
    )


def rate_limited_frame(user_id: str, retry_after: int) -> dict:
    """Told straight to the socket that sent too fast, not through the pipeline:
    it is about this connection, and nobody else needs to hear it."""
    unit = "second" if retry_after == 1 else "seconds"
    event = Event(
        event_type=EventType.NOTIFICATION,
        sender_id=user_id,
        target_type=TargetType.USER,
        target_id=user_id,
        text=f"You are sending messages too quickly. Wait {retry_after} {unit}.",
        metadata={
            "action": EventAction.RATE_LIMITED.value,
            "retry_after": retry_after,
        },
    )
    return event.model_dump(mode="json")


def _uuid(value: Any) -> str | None:
    try:
        return str(UUID(str(value)))
    except ValueError:
        return None


def _valid_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        normalised = _uuid(item)
        # Twice in one list would claim once and then fail the null check,
        # which is harmless, but it would also log a spurious warning.
        if normalised and normalised not in ids:
            ids.append(normalised)
    return ids
