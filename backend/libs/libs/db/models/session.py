from datetime import datetime
from typing import Optional

from libs.db.base import Base, generate_id, generate_timestamp
from sqlalchemy import UUID, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class RefreshToken(Base):
    """One issued refresh token. Rotation is the point of every column here.

    There was a `RefreshToken` before, deleted in Phase 3 and its table dropped
    by revision `b1c4d2f70a91`: it was never imported, never queried, and its
    `user_id` was an Integer FK against a UUID `users.id`, so it could not have
    worked. This is not that model. If you are comparing them, the differences
    that matter are the FK type, the fact that the raw token is never stored,
    and `family_id`.

    **The row holds a SHA-256 of the token, not the token.** The token itself is
    48 random bytes handed to exactly one browser, so a database dump must not
    be a set of working sessions. It is a fast hash on purpose: bcrypt exists to
    slow down guessing a *low*-entropy secret, and there is nothing to guess
    here — it would only add ~60ms to every refresh.

    **`family_id` is what makes theft detectable.** Every rotation issues the
    successor into the same family, so a token presented after it has already
    been rotated away means two parties hold the same session: the legitimate
    one and whoever copied it. There is no way to tell which is which, so the
    whole family is revoked and both have to sign in again. Without the family
    column the best available response would be to revoke the single stolen
    token, which is the one the attacker has already spent.

    Rows are kept after revocation, and that is deliberate: a revoked row is
    exactly what reuse detection reads. `AuthService` deletes a user's expired
    rows on each successful rotation, which is the only cleanup there is.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        UUID, primary_key=True, index=True, default=generate_id
    )
    user_id: Mapped[str] = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Every token descended from one sign-in. Not a FK: the first token in a
    # family names the family, and pointing at a row that may be deleted by the
    # expiry sweep would take the family with it.
    family_id: Mapped[str] = mapped_column(UUID, index=True, default=generate_id)
    # Hex SHA-256, so exactly 64 characters. Unique because a collision would
    # mean one token authenticating two sessions.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=generate_timestamp
    )
    # Inherited unchanged by each successor, so a family expires a fixed time
    # after the sign-in that started it rather than living forever on use. See
    # `AuthService.rotate_session`.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Set by rotation, by logout, and by reuse detection revoking a family.
    # Null means this is the live token of its family.
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
