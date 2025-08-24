import asyncio
import time

import structlog
from libs.event.schema import EventType
from src.redis_manager import RedisManager

logger = structlog.get_logger(__name__)


class GrpcEndpointCache:
    def __init__(self):
        self.endpoint_cache = {}
        self.cache_ttl = 30  # 30 seconds - short enough to handle reconnections
        self.cache_cleanup_interval = 60  # Cleanup every minute
        self.redis_manager: RedisManager | None = None
        self.running = True

    async def set_redis_manager(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager

    async def start(self):
        self.cleanup_task = asyncio.create_task(self._cleanup_cache())

    async def stop(self):
        self.running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()

    async def get_cached_endpoints(self, receiver_id: str, event_type: str):
        cache_key = f"{receiver_id}:{event_type}"
        current_time = time.time()

        # Check cache
        if cache_key in self.endpoint_cache:
            cached_time, endpoints = self.endpoint_cache[cache_key]
            if current_time - cached_time < self.cache_ttl:
                logger.debug("Returning cached endpoints for %s", cache_key)
                return endpoints

        # Fetch from Redis
        if event_type == EventType.NOTIFICATION.value:
            endpoints = await self.redis_manager.get_grpc_endpoint_for_user(receiver_id)
        else:
            endpoints = await self.redis_manager.get_grpc_endpoints_for_channel(
                receiver_id
            )

        # Cache with timestamp
        self.endpoint_cache[cache_key] = (current_time, endpoints)
        logger.debug("Cache missed for %s, fetched %s from Redis", cache_key, endpoints)
        return endpoints

    async def _cleanup_cache(self):
        """Periodic cache cleanup to prevent memory leaks."""
        while self.running:
            await asyncio.sleep(self.cache_cleanup_interval)
            current_time = time.time()
            expired_keys = [
                key
                for key, (cached_time, _) in self.endpoint_cache.items()
                if current_time - cached_time > self.cache_ttl
            ]
            for key in expired_keys:
                del self.endpoint_cache[key]
            if expired_keys:
                logger.debug("Cleaned up %s expired cache entries", len(expired_keys))
