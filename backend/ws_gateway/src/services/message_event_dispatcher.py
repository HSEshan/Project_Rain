from datetime import datetime, timezone
from typing import List
from uuid import uuid4

import structlog
from libs.event.schema import Event
from sqlalchemy import UUID, DateTime, ForeignKey, String, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from src.database.config import Base
from src.database.models import Channel, User

logger = structlog.get_logger()


def generate_id() -> str:
    return str(uuid4())


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(
        UUID, primary_key=True, index=True, default=generate_id
    )
    content: Mapped[str] = mapped_column(String, nullable=False)
    sender_id: Mapped[str] = mapped_column(
        UUID,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[str] = mapped_column(
        UUID,
        ForeignKey("channels.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc)
    )


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
