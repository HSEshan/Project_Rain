from typing import List

import structlog
from libs.db import Attachment, ChannelMember, Message
from libs.event.schema import Event
from libs.media import media_url
from sqlalchemy import insert, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

# Set by the websocket route from the client's frame, read here, and replaced
# with ATTACHMENTS_KEY before the event is published. Clients never see it.
ATTACHMENT_IDS_KEY = "attachment_ids"
# What recipients get: the attachments that were actually claimed, as the same
# objects `GET /messages/{channel_id}` returns.
ATTACHMENTS_KEY = "attachments"


class MessageEventDispatcher:

    async def authorized(
        self, session: AsyncSession, events: List[Event]
    ) -> List[Event]:
        """The events whose sender is a member of the channel they address.

        Nothing checked this until 2026-11-04: any signed-in user could post into
        any conversation whose channel id they knew, and it was stored and
        delivered as if they belonged there.

        Against Postgres rather than the gateway's mapping, because that mapping
        is a routing cache: someone removed from a guild would keep their voice
        there until the event reached this instance. One query per batch rather
        than one per message, so the cost does not scale with traffic.

        The rest are dropped, not failed. Failing would roll back everyone else's
        messages in the batch, which is a denial of service with extra steps.
        """
        rows = await session.execute(
            select(ChannelMember.channel_id, ChannelMember.user_id).where(
                ChannelMember.channel_id.in_({e.channel_id for e in events}),
                ChannelMember.user_id.in_({e.sender_id for e in events}),
            )
        )
        members = {(str(channel_id), str(user_id)) for channel_id, user_id in rows}
        allowed = [e for e in events if (e.channel_id, str(e.sender_id)) in members]
        if len(allowed) < len(events):
            logger.warning(
                "Dropped messages from non-members",
                dropped=len(events) - len(allowed),
            )
        return allowed

    async def _insert(self, session: AsyncSession, events: List[Event]) -> None:
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

    async def _insert_isolated(
        self, session: AsyncSession, events: List[Event]
    ) -> List[Event]:
        """Insert the batch, losing only the rows that cannot go in.

        One statement is the fast path and almost always the only one. If it fails,
        each event is retried in its own savepoint. Everyone's messages share this
        transaction, so without this one bad row costs all of them, for good: they
        have not been persisted anywhere else. Ingest and `authorized` reject what
        can be seen coming; this is for what cannot, such as a channel deleted
        between the membership check and the insert.
        """
        try:
            async with session.begin_nested():
                await self._insert(session, events)
            return events
        except DBAPIError:
            logger.warning("Batch insert failed, retrying per event", events=len(events))

        inserted = []
        for event in events:
            try:
                async with session.begin_nested():
                    await self._insert(session, [event])
                inserted.append(event)
            except DBAPIError:
                logger.warning("Dropped a message that could not be stored")
        return inserted

    async def dispatch_events(
        self, session: AsyncSession, events: List[Event]
    ) -> List[Event]:
        """Store the events, and return the ones that were."""
        # Everything can be dropped by `authorized`, and an insert of no rows is
        # not a no-op: it writes one row of defaults, and fails.
        if not events:
            return []
        inserted = await self._insert_isolated(session, events)
        # After the insert, in the same transaction: the attachment rows point
        # at the message, so it has to exist first, and a rollback of the batch
        # un-claims them along with it.
        for event in inserted:
            await self._claim_attachments(session, event)
        logger.debug(f"Message events dispatched: {inserted}")
        return inserted

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
