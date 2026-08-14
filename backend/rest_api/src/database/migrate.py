"""Schema migration entry point.

The schema used to come from `Base.metadata.create_all` on rest_api startup,
which could only ever add tables — it silently ignored column and constraint
changes, and ws_gateway just assumed the result existed. Alembic owns it now.

rest_api is the only service that migrates. `run_migrations` is called from the
startup event, before the app serves traffic; ws_gateway waits on rest_api's
healthcheck in compose.
"""

from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, inspect
from sqlalchemy.ext.asyncio import AsyncEngine

logger = structlog.get_logger()

# /app/alembic.ini — src/database/migrate.py is three levels down
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _alembic_config(connection: Connection) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    # env.py runs against this connection instead of opening its own engine
    config.attributes["connection"] = connection
    return config


def _upgrade(connection: Connection) -> None:
    config = _alembic_config(connection)
    current = MigrationContext.configure(connection).get_current_revision()
    existing_tables = set(inspect(connection).get_table_names()) - {"alembic_version"}

    if current is None and existing_tables:
        # A database built by the old create_all path. Its tables already match
        # the initial revision, so record that one as done rather than replaying
        # a CREATE TABLE that would fail on every table. Everything after it
        # still runs, which is how such a database picks up later changes.
        baseline = ScriptDirectory.from_config(config).get_base()
        logger.warning(
            "Existing schema with no alembic version, stamping baseline",
            baseline=baseline,
            tables=len(existing_tables),
        )
        command.stamp(config, baseline)

    command.upgrade(config, "head")


async def run_migrations(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(_upgrade)
    logger.info("Database schema is at head")
