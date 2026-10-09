"""What a client is allowed to put in an event it sends over the socket.

The socket builds an `Event` straight from the client's JSON, which means every
field is attacker-supplied, including `metadata`. Before this, a client could
set any metadata key on a message and every recipient would receive it
verbatim, and the gateway itself reads `channels_changed` out of metadata to
decide whose routing to rebuild. So metadata from a client is rebuilt here, not
filtered: the only thing a client may say in it is which of its own uploads to
attach, and even that is only a request the dispatcher checks.
"""

from uuid import UUID

from libs.db import MAX_ATTACHMENTS_PER_MESSAGE
from libs.event.schema import Event, EventType
from src.message.dispatcher import ATTACHMENT_IDS_KEY


def sanitize_client_event(event: Event) -> Event | None:
    """The event as it may enter the pipeline, or None to drop it."""
    requested = (event.metadata or {}).get(ATTACHMENT_IDS_KEY)
    event.metadata = None

    if event.event_type is not EventType.MESSAGE:
        return event

    attachment_ids = _valid_ids(requested)[:MAX_ATTACHMENTS_PER_MESSAGE]
    # A message needs text or at least one image. Whitespace alone is nothing,
    # and would persist a row that renders as an empty bubble.
    if not event.text.strip() and not attachment_ids:
        return None
    if attachment_ids:
        event.metadata = {ATTACHMENT_IDS_KEY: attachment_ids}
    return event


def _valid_ids(value) -> list[str]:
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        try:
            normalised = str(UUID(str(item)))
        except ValueError:
            continue
        # Twice in one list would claim once and then fail the null check,
        # which is harmless, but it would also log a spurious warning.
        if normalised not in ids:
            ids.append(normalised)
    return ids
