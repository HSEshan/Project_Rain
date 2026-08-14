from datetime import datetime

from libs.db.base import Base, generate_id, generate_timestamp
from sqlalchemy import UUID, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class Friendship(Base):
    __tablename__ = "friendships"

    user_1_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id"), primary_key=True, index=True
    )
    user_2_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp
    )


class FriendRequest(Base):
    __tablename__ = "friend_requests"

    id: Mapped[str] = mapped_column(
        UUID, primary_key=True, index=True, default=generate_id
    )
    from_user_id: Mapped[str] = mapped_column(UUID, ForeignKey("users.id"), index=True)
    to_user_id: Mapped[str] = mapped_column(UUID, ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp
    )
