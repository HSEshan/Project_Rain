from typing import List

import structlog
from libs.event.schema import Event
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from src.message.models import Message

logger = structlog.get_logger()


class MessageEventDispatcher:

    async def dispatch_events(self, session: AsyncSession, events: List[Event]):
        await session.execute(
            insert(Message),
            [
                {
                    "id": e.event_id,
                    "sender_id": e.sender_id,
                    "channel_id": e.receiver_id,
                    "content": e.text,
                }
                for e in events
            ],
        )
        logger.debug(f"Message events dispatched: {events}")
