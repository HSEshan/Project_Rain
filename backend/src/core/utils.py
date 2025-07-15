import asyncio
import logging

from src.database.core import Base, engine

logger = logging.getLogger()


async def startup_event():
    async with engine.begin() as conn:
        logger.info("Creating Tables...")
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Startup Successful")


async def shutdown_event():
    await asyncio.sleep(1)
    logger.info("Shutdown Successful")
