import asyncio
import os
from uuid import uuid4

import structlog
from libs.logging import setup_logging
from src.config import config
from src.redis_manager import RedisManager
from src.stream_consumer import RedisStreamConsumer

log_format = os.getenv("LOG_FORMAT", "json")
log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(service_name="event_consumer", log_format=log_format, level=log_level)


async def main():
    """
    Main function with proper startup and shutdown.
    """

    logger = structlog.get_logger(__name__)
    redis_manager = None
    consumer = None

    try:
        redis_manager = RedisManager()
        await redis_manager.connect(
            host=config.redis_host, port=config.redis_port, db=config.redis_db
        )

        consumer = RedisStreamConsumer(consumer_id=str(uuid4()))
        consumer.set_redis_manager(redis_manager)
        await consumer.start()

        heartbeat_task = asyncio.create_task(consumer.heartbeat_loop())
        consume_task = asyncio.create_task(consumer.consume_loop())

        await asyncio.gather(heartbeat_task, consume_task)

        logger.info(f"Consumer started with ID: {consumer.consumer_id}")
        logger.info(f"Config: {config}")

    except Exception as e:
        logger.critical(f"Service error: {e}")
        raise
    finally:
        if consumer:
            await consumer.stop()
        if redis_manager:
            await redis_manager.disconnect()
        logger.info("Service stopped")


if __name__ == "__main__":
    asyncio.run(main())
