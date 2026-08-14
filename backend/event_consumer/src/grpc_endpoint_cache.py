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
                logger.debug(
                    "Returning cached endpoints",
                    user_id=receiver_id,
                    cache_key=cache_key,
                )
                return endpoints

        # Fetch from Redis — receiver_id is a user id for some event types and a
        # channel id for others (libs.event.schema owns that distinction)
        if EventType.is_user_addressed(event_type):
            endpoints = await self.redis_manager.get_grpc_endpoint_for_user(receiver_id)
        else:
            endpoints = await self.redis_manager.get_grpc_endpoints_for_channel(
                receiver_id
            )

        # Only cache a positive result. "Nobody is connected" is the one answer
        # that changes the instant a client reconnects, and caching it for 30s
        # means every event to that channel is dropped for the rest of the
        # window even though the gateway has already re-registered itself — a
        # page refresh was enough to silence a channel.
        if endpoints:
            self.endpoint_cache[cache_key] = (current_time, endpoints)
        else:
            self.endpoint_cache.pop(cache_key, None)

        logger.debug(
            "Fetched endpoints from Redis", receiver_id=receiver_id, endpoints=endpoints
        )
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
                logger.debug(
                    "Cleaned up expired cache entries",
                    num_expired_keys=len(expired_keys),
                )
