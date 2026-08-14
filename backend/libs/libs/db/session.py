from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Both services ran an identical copy of this engine config. Keep one.
DEFAULT_ENGINE_KWARGS = dict(
    echo=False,
    pool_size=2,
    max_overflow=15,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)


def create_engine(async_db_url: str, **overrides) -> AsyncEngine:
    return create_async_engine(async_db_url, **{**DEFAULT_ENGINE_KWARGS, **overrides})


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
