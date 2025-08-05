import asyncio
import os
from asyncio.exceptions import CancelledError

import structlog
from libs.logging import setup_logging
from src.config import config
from src.lease_manager import LeaseManager

log_format = os.getenv("LOG_FORMAT", "json")
log_level = os.getenv("LOG_LEVEL", "INFO")


async def main():
    setup_logging(service_name="lease_manager", log_format=log_format, level=log_level)

    logger = structlog.get_logger(__name__)

    logger.info("Starting...")
    lease_manager = LeaseManager()
    await lease_manager.connect(
        host=config.redis_host, port=config.redis_port, db=config.redis_db
    )
    try:
        await lease_manager.run()
    except (KeyboardInterrupt, CancelledError):
        logger.info("Shutting down...")
    finally:
        lease_manager.running = False
        await lease_manager.disconnect()
        logger.info("Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
