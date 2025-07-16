import asyncio
import logging

from sqlalchemy import text
from src.database.core import Base, engine

logger = logging.getLogger("lifespan")


async def startup_event():
    # Check database connection first
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

    async with engine.begin() as conn:
        logger.info("Creating Tables...")
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Startup Successful")


async def shutdown_event():
    await asyncio.sleep(1)
    logger.info("Shutdown Successful")
