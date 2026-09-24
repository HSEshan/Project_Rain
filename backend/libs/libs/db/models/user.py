from datetime import datetime
from typing import Optional

from libs.db.base import Base, generate_id, generate_timestamp
from sqlalchemy import UUID, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

# How long a bio may be, in one place: the column length and the validator that
# rejects a longer one read the same number, so they cannot drift into a
# database error where there should have been a 422.
#
# 190 is Discord's limit for the same field. There is no principled number here
# and any cap is arbitrary, so the one worth picking is the one people already
# have a feel for, and it is comfortably a couple of sentences.
BIO_MAX_LENGTH = 190


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID, primary_key=True, index=True, default=generate_id
    )
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    # The first thing a user may say about themselves. Nullable rather than
    # defaulted to "": null means "never wrote one", which is what the card
    # renders a prompt for, and it is also what clearing a bio returns to.
    bio: Mapped[Optional[str]] = mapped_column(
        String(BIO_MAX_LENGTH), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=generate_timestamp,
        onupdate=generate_timestamp,
    )
