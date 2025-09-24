from datetime import datetime

from sqlalchemy import UUID, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from src.database.config import Base
from src.utils.default import generate_id, generate_timestamp


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
        DateTime(timezone=True), default=generate_timestamp
    )
