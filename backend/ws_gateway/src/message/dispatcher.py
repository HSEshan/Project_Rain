from typing import List

import structlog
from libs.db import Attachment, Message
from libs.event.schema import Event
from libs.media import media_url
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

# Set by the websocket route from the client's frame, read here, and replaced
# with ATTACHMENTS_KEY before the event is published. Clients never see it.
ATTACHMENT_IDS_KEY = "attachment_ids"
# What recipients get: the attachments that were actually claimed, as the same
# objects `GET /messages/{channel_id}` returns.
ATTACHMENTS_KEY = "attachments"


class MessageEventDispatcher:

    async def dispatch_events(self, session: AsyncSession, events: List[Event]):
        await session.execute(
            insert(Message),
            [
                {
                    "id": e.event_id,
                    "sender_id": e.sender_id,
                    # Asserts the event is channel-addressed rather than
                    # trusting the raw id: a user-addressed event reaching here
                    # would otherwise write a row whose channel_id is a user id
                    "channel_id": e.channel_id,
                    "content": e.text,
                }
                for e in events
            ],
        )
        # After the insert, in the same transaction: the attachment rows point
        # at the message, so it has to exist first, and a rollback of the batch
        # un-claims them along with it.
        for event in events:
            await self._claim_attachments(session, event)
        logger.debug(f"Message events dispatched: {events}")

    async def _claim_attachments(self, session: AsyncSession, event: Event):
        """Link the sender's uploads to this message, and tell recipients about them.

        An id is only claimed if it belongs to the sender and no message has it
        yet. The ids came from a client, so this is the authorisation: without
        the uploader check, anyone who saw an attachment id could attach
        someone else's image to their own message; without the null check, one
        upload could be moved from message to message. Ids that fail either
        check are dropped rather than failing the message, which still sends.

        One UPDATE per id (at most MAX_ATTACHMENTS_PER_MESSAGE) because each
        gets its own position, and the order the client listed them in is the
        order the gallery shows.
        """
        requested = (event.metadata or {}).pop(ATTACHMENT_IDS_KEY, None) or []
        if not requested:
            return

        claimed = []
        for position, attachment_id in enumerate(requested):
            result = await session.execute(
                update(Attachment)
                .where(
                    Attachment.id == attachment_id,
                    Attachment.uploader_id == event.sender_id,
                    Attachment.message_id.is_(None),
                )
                .values(message_id=event.event_id, position=position)
                .returning(
                    Attachment.id,
                    Attachment.key,
                    Attachment.content_type,
                    Attachment.width,
                    Attachment.height,
                    Attachment.size_bytes,
                )
            )
            row = result.first()
            if row is None:
                continue
            claimed.append(
                {
                    "id": str(row.id),
                    "url": media_url(row.key),
                    "content_type": row.content_type,
                    "width": row.width,
                    "height": row.height,
                    "size_bytes": row.size_bytes,
                }
            )

        if len(claimed) < len(requested):
            logger.warning(
                "Some attachments were not claimable",
                requested=len(requested),
                claimed=len(claimed),
                message_id=event.event_id,
            )
        event.metadata = {**(event.metadata or {}), ATTACHMENTS_KEY: claimed}
