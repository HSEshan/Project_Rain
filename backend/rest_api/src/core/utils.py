import asyncio

import structlog
from sqlalchemy import text
from src.core.config import settings
from src.database.core import engine
from src.database.migrate import run_migrations
from src.realtime.publisher import realtime_publisher

logger = structlog.get_logger()


async def startup_event():
    # Check database connection first
    retries = 5
    while retries > 0:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info(
                f"Database connection verified: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}"
            )
            break
        except Exception as e:
            logger.error(
                f"Database connection failed, retrying... {retries} retries left",
                error=e,
            )
            retries -= 1
            await asyncio.sleep(2)
            if retries == 0:
                raise e
    if retries == 0:
        raise Exception("Database connection failed")

    await run_migrations(engine)

    # Best effort: a missing Redis degrades realtime updates, it does not stop
    # the API from serving
    await realtime_publisher.connect()
    logger.info("Startup Successful")


async def shutdown_event():
    await realtime_publisher.disconnect()
    await asyncio.sleep(1)
    logger.info("Shutdown Successful")
