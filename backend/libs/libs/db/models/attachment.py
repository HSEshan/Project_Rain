from datetime import datetime
from typing import Optional

from libs.db.base import Base, generate_id, generate_timestamp
from sqlalchemy import UUID, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

# How many images one message may carry. A table rather than a column on
# `messages` is what makes "several" possible at all; this is what stops
# "several" meaning a hundred. Read by the gateway when it claims uploads for a
# message and by the client that builds the composer, so it lives beside the
# table.
MAX_ATTACHMENTS_PER_MESSAGE = 4


class Attachment(Base):
    """One image, uploaded before the message that carries it exists.

    Messages are written over the websocket, which cannot carry a file, so an
    attachment is uploaded first over REST and *claimed* by a message after:
    the client sends the ids along with the text, and the gateway links every
    one that belongs to the sender and is still unclaimed. Until then
    `message_id` is null.

    **A null `message_id` is also where orphans go.** The foreign key is
    `SET NULL`, not `CASCADE`, so deleting a message (a demo reset, the last
    member leaving a group DM, a future "delete message") turns its attachments
    back into unclaimed rows instead of deleting them. The row still holds the
    storage key, and the sweep in rest_api's media service deletes the object
    and the row once it has sat unclaimed for an hour. A cascade would have
    deleted the only record of which object to remove, and the bucket would
    grow forever.
    """

    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(
        UUID, primary_key=True, index=True, default=generate_id
    )
    uploader_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[Optional[str]] = mapped_column(
        UUID,
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Order within the message, so a gallery renders the way it was composed
    position: Mapped[int] = mapped_column(Integer, default=0)
    key: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Stored so the client can reserve the space before the image loads; a
    # chat that jumps as each picture arrives scrolls you away from the bottom.
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp, index=True
    )
