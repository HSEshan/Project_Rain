import asyncio

import structlog
from sqlalchemy import text
from src.core.config import settings
from src.database.core import Base, engine

logger = structlog.get_logger()


async def startup_event():
    # Check database connection first
    logger.debug(settings)
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

    async with engine.begin() as conn:
        logger.info("Creating Tables...")
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Startup Successful")


async def shutdown_event():
    await asyncio.sleep(1)
    logger.info("Shutdown Successful")
