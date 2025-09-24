import asyncio
import time

import structlog
from src.config import config
from src.grpc_connection_pool import GrpcConnectionPool
from src.grpc_endpoint_cache import GrpcEndpointCache
from src.redis_manager import RedisManager
from src.stream_worker import StreamWorker

logger = structlog.get_logger(__name__)


class RedisStreamConsumer:
    """
    Redis stream consumer service. It consumes events from Redis streams, identifies gRPC endpoints from Redis,
    and sends events to the gRPC endpoints.
    """

    def __init__(self, consumer_id: str):
        self.redis_manager: RedisManager | None = None
        self.consumer_id = consumer_id
        self.fetched_shards: list[str] = []
        self.consumer_group = "grpc_group"
        self.running = True
        self.connection_pool = GrpcConnectionPool(
            max_connections=config.max_grpc_connections,
        )
        self.shard_workers: dict[str, StreamWorker] = {}
        self.grpc_endpoint_cache = GrpcEndpointCache()

    def set_redis_manager(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager

    async def start(self):
        """Start the consumer and connection pool."""
        try:
            await self.connection_pool.start()
            await self.register()
            await self.grpc_endpoint_cache.set_redis_manager(self.redis_manager)
            await self.grpc_endpoint_cache.start()

        except Exception as e:
            logger.critical(
                "Error starting consumer", consumer_id=self.consumer_id, error=e
            )
            raise

    async def stop(self):
        """Stop the consumer and cleanup connections."""
        self.running = False
        for worker in self.shard_workers.values():
            await worker.stop()
        self.shard_workers.clear()
        await self.connection_pool.stop()
        await self.grpc_endpoint_cache.stop()

        await self.unregister()
        logger.info("Consumer stopped", consumer_id=self.consumer_id)

    async def register(self):
        await self.redis_manager.register_consumer(self.consumer_id)
        await self.redis_manager.send_heartbeat(self.consumer_id, ttl=15)
        logger.info("Consumer registered", consumer_id=self.consumer_id)

    async def unregister(self):
        await self.redis_manager.unregister_consumer(self.consumer_id)
        logger.info("Consumer unregistered", consumer_id=self.consumer_id)

    async def heartbeat_loop(self):
        next_heartbeat = time.monotonic()
        while self.running:
            # Send heartbeat
            await self.redis_manager.send_heartbeat(self.consumer_id, ttl=15)
            # Avoid drift
            next_heartbeat += 5
            sleep_duration = max(0, next_heartbeat - time.monotonic())
            await asyncio.sleep(sleep_duration)

    async def consume_loop(self):
        while self.running:
            try:
                # Add timeout to prevent blocking indefinitely
                current_fetched_shards = await asyncio.wait_for(
                    self.redis_manager.fetch_leased_shards(self.consumer_id),
                    timeout=5.0,  # 5 second timeout
                )

                if current_fetched_shards != self.fetched_shards:
                    self.fetched_shards = current_fetched_shards
                    logger.info(
                        "Fetched shards updated", fetched_shards=self.fetched_shards
                    )

                # Create workers to read from each stream. Update on each lease call.
                for shard in self.fetched_shards:
                    if shard in self.shard_workers:
                        continue
                    try:
                        self.shard_workers[shard] = StreamWorker(
                            shard,
                            self.consumer_id,
                            self.connection_pool,
                            self.grpc_endpoint_cache,
                            self.redis_manager,
                        )
                        self.shard_workers[shard].start()
                    except Exception as e:
                        logger.error("Error launching worker for shard", shard=shard)
                        await asyncio.sleep(1)
                    logger.debug("Launched worker for shard", shard=shard)

                # Cleanup tasks that are not in the shards list
                for shard in list(self.shard_workers.keys()):
                    if shard not in self.fetched_shards:
                        await self.shard_workers[shard].stop()
                        del self.shard_workers[shard]
                        logger.debug("Stopped worker for shard", shard=shard)

                await asyncio.sleep(0.1)

            except asyncio.TimeoutError:
                logger.warning("Timeout fetching leased shards, retrying...")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error("Error in consume loop", error=e)
                await asyncio.sleep(1)

        logger.warning("Consume loop stopped")
