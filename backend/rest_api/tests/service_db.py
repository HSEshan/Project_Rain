"""A real database for service tests, without a stack: SQLite in memory.

The services are where the authorization rules actually run (`require_permission`,
the rank checks, the ban check in `join_guild`, the friends-only rule), and they
are written against SQLAlchemy queries, not an interface a fake could stand in
for. So these tests give them a real database, just not Postgres.

Two adaptations make the shared models behave on SQLite the way they do on
Postgres, and both live here rather than in the models:

- **UUIDs stay strings.** The models use `UUID` columns but pass `str` ids
  everywhere. On Postgres asyncpg accepts either; SQLAlchemy's non-native UUID
  path calls `.hex` on the value and fails on a `str`. Telling the dialect it has
  native UUIDs makes it pass values through untouched, which is what the code
  expects (it `str()`s every id it reads back).
- **Datetimes come back timezone-aware.** SQLite has no timezone type, so a
  `DateTime(timezone=True)` comes back naive and the code's comparisons against
  `datetime.now(timezone.utc)` would raise. Every value is stored as UTC and
  read back with UTC attached.

What SQLite cannot reproduce: `FOR UPDATE` (ignored), and concurrency in general.
The one-statement link spend and the rotation lock are therefore checked for their
logic here, not for their behaviour under a race; the e2e suite covers those.

Needs `aiosqlite`, which is not in the service images; the tests that use this
skip without it.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import timezone
from typing import Any

import pytest

aiosqlite = pytest.importorskip("aiosqlite")

from libs.db import (  # noqa: E402
    Base,
    Channel,
    ChannelMember,
    ChannelType,
    Friendship,
    GuildMember,
    GuildMemberRole,
    GuildMemberStatus,
    User,
    generate_id,
)
from sqlalchemy import DateTime, event  # noqa: E402
from sqlalchemy.dialects.sqlite import DATETIME as SQLITE_DATETIME  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402
from src.auth.utils import CurrentUser  # noqa: E402
from src.guild.repository import GuildRepository  # noqa: E402
from src.guild.schemas import GuildCreate  # noqa: E402


class UTCDateTime(SQLITE_DATETIME):
    """SQLite's DATETIME, but aware on the way out and UTC on the way in."""

    def bind_processor(self, dialect):
        parent = super().bind_processor(dialect)

        def process(value):
            if value is not None and value.tzinfo is not None:
                value = value.astimezone(timezone.utc).replace(tzinfo=None)
            return parent(value) if parent else value

        return process

    def result_processor(self, dialect, coltype):
        parent = super().result_processor(dialect, coltype)

        def process(value):
            value = parent(value) if parent else value
            if value is not None and value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value

        return process


def run(coro):
    """The services are async and these tests are not; no pytest-asyncio here."""
    return asyncio.run(coro)


class World:
    """One test's database, and the shortest way to put people in it."""

    def __init__(self, engine):
        self.engine = engine
        self.sessions = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )

    def session(self) -> AsyncSession:
        return self.sessions()

    async def call(self, service_cls, method: str, *args, **kwargs) -> Any:
        """A fresh session per call, the way a request gets one.

        The services open their own transaction with `db.begin()`, which raises
        on a session that has already autobegun one.
        """
        async with self.session() as db:
            return await getattr(service_cls(db), method)(*args, **kwargs)

    async def scalar(self, statement):
        async with self.session() as db:
            return (await db.execute(statement)).scalar_one_or_none()

    async def scalars(self, statement):
        async with self.session() as db:
            return list((await db.execute(statement)).scalars().all())

    async def user(self, name: str) -> CurrentUser:
        user_id = generate_id()
        async with self.session() as db:
            db.add(
                User(
                    id=user_id,
                    username=name,
                    email=f"{name}@example.test",
                    password_hash="not-a-real-hash",
                )
            )
            await db.commit()
        return CurrentUser(id=user_id, name=name, email=f"{name}@example.test")

    async def guild(self, owner: CurrentUser, name: str = "Guild") -> str:
        """A guild as `create_guild` makes one: owner with an ADMIN row, two
        channels, the owner in both."""
        async with self.session() as db:
            guild = await GuildRepository.create_guild(
                db, GuildCreate(name=name, description="d"), owner
            )
            await db.commit()
            return str(guild.id)

    async def member(
        self,
        guild_id: str,
        user: CurrentUser,
        role: GuildMemberRole = GuildMemberRole.MEMBER,
    ) -> None:
        """Join the way an invite does, then set the role."""
        async with self.session() as db:
            await GuildRepository.join_guild(db, guild_id, user.id)
            if role != GuildMemberRole.MEMBER:
                row = await db.get(GuildMember, (guild_id, user.id))
                row.role = role
            await db.commit()

    async def friends(self, a: CurrentUser, b: CurrentUser) -> None:
        low, high = sorted([str(a.id), str(b.id)])
        async with self.session() as db:
            db.add(Friendship(user_1_id=low, user_2_id=high))
            await db.commit()

    async def channel(
        self, type: ChannelType, *members: CurrentUser, guild_id: str | None = None
    ) -> str:
        channel_id = generate_id()
        async with self.session() as db:
            db.add(
                Channel(
                    id=channel_id,
                    type=type,
                    guild_id=guild_id,
                    owner_id=str(members[0].id) if type == ChannelType.GROUP_DM else None,
                )
            )
            await db.flush()
            for member in members:
                db.add(ChannelMember(channel_id=channel_id, user_id=member.id))
                await db.flush()
            await db.commit()
        return channel_id

    async def guild_channels(self, guild_id: str) -> list[Channel]:
        async with self.session() as db:
            return await GuildRepository.get_guild_channels(db, guild_id)


@asynccontextmanager
async def world():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    # See the module docstring for why each of these.
    engine.sync_engine.dialect.supports_native_uuid = True
    engine.sync_engine.dialect.colspecs = {
        **engine.sync_engine.dialect.colspecs,
        DateTime: UTCDateTime,
    }

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys(dbapi_connection, _record):
        # Postgres enforces them; without this SQLite silently would not, and a
        # delete in the wrong order would pass here and fail in production.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield World(engine)
    finally:
        await engine.dispose()


class Recorder:
    """Stands in for the realtime publisher, LiveKit and storage side effects."""

    def __init__(self):
        self.events = []
        self.invalidated: list[str] = []
        self.removed_from_rooms: list[tuple[list[str], str]] = []
        self.closed_rooms: list[str] = []
        self.deleted_keys: list[str] = []

    async def publish_many(self, events):
        self.events.extend(e for e in events if e is not None)

    async def publish(self, *events):
        await self.publish_many(events)

    async def invalidate_user_channels(self, *user_ids):
        self.invalidated.extend(str(u) for u in user_ids)

    async def remove_from_rooms(self, rooms, user_id):
        self.removed_from_rooms.append((list(rooms), str(user_id)))

    async def close_rooms(self, rooms):
        self.closed_rooms.extend(rooms)

    async def delete_quietly(self, keys):
        self.deleted_keys.extend(k for k in keys if k)

    def recipients(self) -> set[str]:
        return {str(e.target_id or e.receiver_id) for e in self.events}


@pytest.fixture()
def side_effects(monkeypatch) -> Recorder:
    """Every after-commit side effect, recorded instead of performed."""
    from src.channel import service as channel_service
    from src.guild import service as guild_service
    from src.message import service as message_service
    from src.realtime.publisher import realtime_publisher

    recorder = Recorder()
    monkeypatch.setattr(realtime_publisher, "publish_many", recorder.publish_many)
    monkeypatch.setattr(realtime_publisher, "publish", recorder.publish)
    monkeypatch.setattr(
        realtime_publisher, "invalidate_user_channels", recorder.invalidate_user_channels
    )
    for module in (guild_service, channel_service):
        monkeypatch.setattr(module, "remove_from_rooms", recorder.remove_from_rooms)
        monkeypatch.setattr(module, "close_rooms", recorder.close_rooms)
    for module in (guild_service, message_service):
        monkeypatch.setattr(module, "delete_quietly", recorder.delete_quietly)
    return recorder


__all__ = ["GuildMemberStatus", "Recorder", "World", "run", "side_effects", "world"]
