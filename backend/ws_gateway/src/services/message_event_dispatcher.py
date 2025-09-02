from datetime import datetime, timezone
from typing import List

from sqlalchemy import UUID, DateTime, ForeignKey, String, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base

from libs.event.schema import Event


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(UUID, primary_key=True, index=True)
    content: Mapped[str] = mapped_column(String, nullable=False)
    sender_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id"), nullable=False, index=True
    )
    receiver_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("channels.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now(timezone.utc)
    )


class MessageEventDispatcher:

    async def dispatch_event(self, session: AsyncSession, events: List[Event]):
        await session.execute(
            insert(Message),
            [
                {
                    "id": e.event_id,
                    "sender_id": e.sender_id,
                    "receiver_id": e.receiver_id,
                    "content": e.text,
                }
                for e in events
            ],
        )
