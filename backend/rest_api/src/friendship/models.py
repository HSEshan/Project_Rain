from datetime import datetime, timezone

from sqlalchemy import UUID, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.database.core import Base
from src.utils.default import generate_id


class Friendship(Base):
    __tablename__ = "friendships"
    user_1_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id"), primary_key=True, index=True
    )
    user_2_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc)
    )


class FriendRequest(Base):
    __tablename__ = "friend_requests"
    id: Mapped[str] = mapped_column(
        UUID, primary_key=True, index=True, default=generate_id
    )
    from_user_id: Mapped[str] = mapped_column(UUID, ForeignKey("users.id"), index=True)
    to_user_id: Mapped[str] = mapped_column(UUID, ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc)
    )
