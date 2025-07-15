import asyncio
import logging

logger = logging.getLogger()


async def startup_event():

    await asyncio.sleep(1)
    logger.info("Startup Successful")


async def shutdown_event():
    await asyncio.sleep(1)
    logger.info("Shutdown Successful")
