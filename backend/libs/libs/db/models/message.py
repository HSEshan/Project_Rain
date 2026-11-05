from datetime import datetime
from typing import Optional

from libs.db.base import Base, generate_id, generate_timestamp
from sqlalchemy import UUID, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


# Checked at the socket, the only way a message is written. Not on the column:
# Postgres would refuse a longer row, and a bad row fails its whole batch.
MAX_MESSAGE_LENGTH = 4000


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        UUID, primary_key=True, index=True, default=generate_id
    )
    content: Mapped[str] = mapped_column(String, nullable=False)
    sender_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id"), nullable=False, index=True
    )
    channel_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("channels.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp
    )
    # Null for the overwhelming majority, and how the client knows to say so
    edited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
