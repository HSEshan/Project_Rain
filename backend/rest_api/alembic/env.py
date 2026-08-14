import asyncio
from logging.config import fileConfig

from alembic import context
from libs.db import Base  # imports every model, so autogenerate sees them all
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from src.core.config import settings

config = context.config

# When the app drives Alembic it hands us a live connection and owns logging.
external_connection = config.attributes.get("connection")

if config.config_file_name is not None and external_connection is None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ConfigParser interpolates %, and a generated Postgres password may contain one
config.set_main_option("sqlalchemy.url", settings.ASYNC_DB_URL.replace("%", "%%"))


def run_migrations_offline() -> None:
    context.configure(
        url=settings.ASYNC_DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if external_connection is not None:
    # Already inside `await conn.run_sync(...)` — this is a sync Connection
    do_run_migrations(external_connection)
elif context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
