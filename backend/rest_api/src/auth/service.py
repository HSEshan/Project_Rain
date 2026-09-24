from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm
from libs.db import RefreshToken, User, generate_id, generate_timestamp
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.schemas import Token, UserCreate, UserResponse
from src.auth.utils import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    parse_login_method,
)
from src.core.config import settings
from src.database.core import get_db
from src.database.service import BaseService
from src.utils.exceptions import (
    AlreadyExistsException,
    NotFoundException,
    UnauthorizedException,
)
from src.utils.hashing import (
    DUMMY_PASSWORD_HASH,
    get_password_hash,
    verify_password,
)

logger = structlog.get_logger()


@dataclass
class IssuedSession:
    """Both halves of a session, for the route that has the `Response`.

    The refresh token is a raw string exactly once, here, on its way into a
    `Set-Cookie`. Nothing stores it and nothing logs it: the database has only
    its hash, and this object does not outlive the request.
    """

    access_token: Token
    refresh_token: str
    refresh_expires_at: datetime


class AuthService(BaseService):

    async def get_user_by_id(self, user_id: str) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException("User not found")
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).filter(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).filter(User.username == username))
        return result.scalar_one_or_none()

    async def register_user(self, user: UserCreate) -> UserResponse:
        async with self.db.begin():
            user_exists = await self.get_user_by_email(user.email)
            if user_exists:
                raise AlreadyExistsException("User with this email already exists")
            user_exists = await self.get_user_by_username(user.username)
            if user_exists:
                raise AlreadyExistsException("User with this username already exists")

            user = User(
                email=user.email,
                username=user.username,
                password_hash=await get_password_hash(user.password),
            )
            self.db.add(user)
            await self.db.flush()
            await self.db.refresh(user)
        return UserResponse(id=str(user.id), username=user.username, email=user.email)

    async def login_user(self, form_data: OAuth2PasswordRequestForm) -> IssuedSession:
        """One answer for "no such account" and "wrong password".

        It used to be two: 404 for an unknown account, 401 for a bad password.
        That turns the sign-in form into an oracle — submit an email, read the
        status code, learn whether someone has an account here — which is worth
        nothing to a person signing in and quite a lot to someone building a
        list of targets. The UI already showed one message for both; this makes
        the API agree, because the status code was the half that actually
        leaked.

        The comparison is deliberately still run against a dummy hash when the
        account does not exist. Without it, an unknown email returns in
        microseconds and a real one takes the ~60ms bcrypt costs, and the same
        question is answered by a stopwatch instead.
        """
        login_method = parse_login_method(form_data.username)
        if login_method == "email":
            user_to_login = await self.get_user_by_email(form_data.username.lower())
        else:
            user_to_login = await self.get_user_by_username(form_data.username)

        password_hash = (
            user_to_login.password_hash if user_to_login else DUMMY_PASSWORD_HASH
        )
        password_ok = await verify_password(
            plain_password=form_data.password,
            hashed_password=password_hash,
        )
        if not user_to_login or not password_ok:
            raise UnauthorizedException("Incorrect email or password")

        return await self.issue_session(user_to_login)

    async def delete_user(self, user_id: str):
        user = await self.get_user_by_id(user_id)
        await self.db.delete(user)
        await self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Sessions (Phase 15)
    #
    # Three entry points, one shape: `issue_session` starts a family at
    # sign-in, `rotate_session` moves it forward, `revoke_session` ends it.
    # Everything else here is private and exists to keep those three honest.
    # ------------------------------------------------------------------

    async def issue_session(self, user: User) -> IssuedSession:
        """A fresh family. Called by sign-in, and by the demo login."""
        expires_at = generate_timestamp(timedelta(days=settings.REFRESH_TOKEN_DAYS))
        raw = self._add_refresh_token(
            user_id=str(user.id), family_id=generate_id(), expires_at=expires_at
        )
        # An explicit commit rather than `async with self.db.begin()`. The
        # caller has already run selects on this session, so the transaction is
        # open — opening another raises "transaction already begun", which is
        # the Phase 1 bug that cost an afternoon in `create_guild_channel`.
        await self.db.commit()

        access = await create_access_token(str(user.id), user.email, user.username)
        return IssuedSession(
            access_token=access, refresh_token=raw, refresh_expires_at=expires_at
        )

    async def rotate_session(self, raw_token: str | None) -> IssuedSession:
        """Spend one refresh token, issue its successor.

        Every failure here is 401 with the same sentence. The client's only
        useful response is to sign in again, and distinguishing "no cookie"
        from "expired" from "we revoked your family because someone replayed a
        token" would tell whoever is holding a stolen token exactly which of
        those happened.
        """
        if not raw_token:
            raise UnauthorizedException("Session expired")

        now = generate_timestamp()
        row = await self._locked_by_hash(hash_refresh_token(raw_token))
        if row is None:
            raise UnauthorizedException("Session expired")

        if row.revoked_at is not None:
            row = await self._resolve_replay(row, now)

        if row.expires_at <= now:
            # The absolute end of the sign-in this family came from. Nothing to
            # revoke: an expired token authenticates nothing either way.
            raise UnauthorizedException("Session expired")

        user = await self._user_for_session(row.user_id)

        row.revoked_at = now
        raw = self._add_refresh_token(
            user_id=row.user_id,
            family_id=row.family_id,
            # Inherited, not extended. This is what makes REFRESH_TOKEN_DAYS an
            # absolute session lifetime rather than an idle timeout: a session
            # in constant use still ends 30 days after the sign-in that started
            # it. Handing the successor a fresh expiry here is the one-line
            # change to sliding sessions, and it means no session ever ends on
            # its own.
            expires_at=row.expires_at,
        )
        await self._delete_expired_for(row.user_id, now)
        await self.db.commit()

        access = await create_access_token(str(user.id), user.email, user.username)
        return IssuedSession(
            access_token=access, refresh_token=raw, refresh_expires_at=row.expires_at
        )

    async def revoke_session(self, raw_token: str | None) -> None:
        """Sign out. Ends the family, not just the token presented.

        The family *is* the session, so leaving its live token valid would mean
        "sign out" logged you out of the tab you clicked it in and nothing
        else. Silent when the token is unknown or already dead: a sign-out that
        can fail is a sign-out people learn to distrust, and there is nothing
        the client could do about the error anyway.
        """
        if not raw_token:
            return
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(raw_token)
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        await self._revoke_family(row.family_id, generate_timestamp())
        await self.db.commit()

    def _add_refresh_token(
        self, user_id: str, family_id: str, expires_at: datetime
    ) -> str:
        """Stage one token and return the raw value. The caller commits."""
        raw = generate_refresh_token()
        self.db.add(
            RefreshToken(
                user_id=user_id,
                family_id=family_id,
                token_hash=hash_refresh_token(raw),
                expires_at=expires_at,
            )
        )
        return raw

    async def _locked_by_hash(self, token_hash: str) -> RefreshToken | None:
        """`FOR UPDATE`, so two rotations of the same token are serialised.

        Without the lock, two requests carrying one token both read
        `revoked_at IS NULL`, both rotate, and the family ends up with two live
        tokens — which is precisely the state reuse detection exists to treat
        as theft. With it, the second waits, re-reads a row that is now
        revoked, and takes the replay path below.
        """
        result = await self.db.execute(
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def _resolve_replay(self, row: RefreshToken, now: datetime) -> RefreshToken:
        """A token that has already been spent. Duplicate request, or theft?

        There is no way to tell them apart from the token alone, so the timing
        decides. Inside the grace window the ordinary explanation is two of the
        user's own tabs waking up together, or a retried request: the family's
        live token is still there and untouched, so the request is served from
        it and nobody is signed out. Outside the window the ordinary
        explanation is that someone kept a copy — the legitimate browser has
        long since moved on — and the whole family goes, because there is no
        way to know which of the two holders is the real one.

        The trade is deliberate and narrow: an attacker who replays a stolen
        token within `REFRESH_REUSE_GRACE_SECONDS` of its legitimate use gets a
        session. They would also win that race by being fractionally faster, so
        the grace window buys them very little, and the alternative costs real
        users their session every time two tabs refresh at once.
        """
        grace = timedelta(seconds=settings.REFRESH_REUSE_GRACE_SECONDS)
        head = await self._family_head(row.family_id)
        if head is not None and row.revoked_at is not None:
            if now - row.revoked_at <= grace:
                logger.info(
                    "Refresh token replayed inside the grace window",
                    user_id=str(row.user_id),
                    family_id=str(row.family_id),
                )
                return head

        logger.warning(
            "Refresh token reuse detected, revoking family",
            user_id=str(row.user_id),
            family_id=str(row.family_id),
            # Whether a live token existed says which case this is: with one,
            # someone replayed an old token against a working session; without,
            # the family was already dead and this is a stale browser.
            had_live_token=head is not None,
        )
        await self._revoke_family(row.family_id, now)
        await self.db.commit()
        raise UnauthorizedException("Session expired")

    async def _family_head(self, family_id: str) -> RefreshToken | None:
        """The one token of a family that has not been rotated away yet."""
        result = await self.db.execute(
            select(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .order_by(RefreshToken.issued_at.desc())
            .with_for_update()
        )
        return result.scalars().first()

    async def _revoke_family(self, family_id: str, now: datetime) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )

    async def _delete_expired_for(self, user_id: str, now: datetime) -> None:
        """The only cleanup there is, and it is enough.

        Revoked rows have to survive their own revocation — they are what reuse
        detection reads — so the table only ever shrinks here. Bounded by one
        user's rows and run on the path that creates them, which means it keeps
        pace without a cron job that nobody would notice had stopped.
        """
        await self.db.execute(
            delete(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.expires_at < now,
            )
        )

    async def _user_for_session(self, user_id: str) -> User:
        """Like `get_user_by_id`, but 401 rather than 404.

        A deleted account takes its tokens with it (`ondelete="CASCADE"`), so
        this should be unreachable; if it ever is reached, the answer a refresh
        owes the client is "sign in again", not "no such user".
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise UnauthorizedException("Session expired")
        return user


def get_auth_service(db: AsyncSession = Depends(get_db)):
    return AuthService(db)
