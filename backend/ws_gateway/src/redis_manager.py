import asyncio
from typing import List, Optional

import structlog
from libs.event.codec import EventCodec
from libs.event.schema import Event
from libs.rediskeys import RediKeys
from redis.asyncio import Redis
from src.core.config import settings

logger = structlog.get_logger()


class RedisManager:
    def __init__(self):
        self.redis: Redis | None = None

    async def connect(self, host: str, port: int, db: int):
        retries = 5
        while retries > 0:
            try:
                self.redis = Redis(host=host, port=port, db=db)
                await self.redis.ping()
                logger.info("Connected to Redis")
                break
            except Exception as e:
                logger.error(
                    f"Failed to connect to Redis, retries left: {retries}",
                    error=e,
                )
                retries -= 1
                await asyncio.sleep(1)

        if retries == 0:
            logger.critical("Failed to connect to Redis, max retries reached")
            raise Exception("Failed to connect to Redis, max retries reached")

    async def disconnect(self):
        if self.redis:
            await self.redis.aclose()
        logger.info("Disconnected from Redis")

    async def set_user_grpc_endpoint(
        self, user_id: str, grpc_endpoint: str, ttl: int = settings.DEFAULT_TTL_SECONDS
    ):
        await self.redis.setex(RediKeys.user_grpc_endpoint(user_id), ttl, grpc_endpoint)

    async def get_user_grpc_endpoint(self, user_id: str) -> Optional[str]:
        return await self.redis.get(RediKeys.user_grpc_endpoint(user_id))

    async def delete_user_grpc_endpoint(self, user_id: str):
        await self.redis.delete(RediKeys.user_grpc_endpoint(user_id))

    async def add_grpc_endpoint_to_channel(
        self,
        channel_id: str,
        grpc_endpoint: str,
        ttl: int = settings.DEFAULT_TTL_SECONDS,
    ):
        key = RediKeys.channel_grpc_endpoints(channel_id)
        await self.redis.sadd(key, grpc_endpoint)
        await self.redis.expire(key, ttl)

    async def remove_grpc_endpoint_from_channel(
        self, channel_id: str, grpc_endpoint: str
    ):
        key = RediKeys.channel_grpc_endpoints(channel_id)
        await self.redis.srem(key, grpc_endpoint)
        if await self.redis.scard(key) == 0:
            await self.redis.delete(key)

    async def add_channel_to_user(
        self, user_id: str, channel_id: str, ttl: int = settings.DEFAULT_TTL_SECONDS
    ):
        key = RediKeys.user_channels(user_id)
        await self.redis.sadd(key, str(channel_id))
        await self.redis.expire(key, ttl)

    async def remove_channel_from_user(self, user_id: str, channel_id: str):
        key = RediKeys.user_channels(user_id)
        await self.redis.srem(key, str(channel_id))
        if await self.redis.scard(key) == 0:
            await self.redis.delete(key)

    async def get_user_channel_ids(self, user_id: str) -> List[str]:
        key = RediKeys.user_channels(user_id)
        if await self.redis.exists(key):
            raw_ids = await self.redis.smembers(key)
            decoded = [cid.decode() for cid in raw_ids]
            logger.info(f"Redis cache for {user_id}: {decoded}")
            return decoded

        channel_ids = await self.query_user_channels_from_db(user_id)
        await self.cache_user_channel_ids(user_id, channel_ids)
        logger.info(f"Cached DB channels for {user_id}: {channel_ids}")
        return channel_ids

    async def cache_user_channel_ids(
        self,
        user_id: str,
        channel_ids: List[str],
        ttl: int = 120,
    ):
        key = RediKeys.user_channels(user_id)
        channel_strs = [str(cid) for cid in channel_ids]
        await self.redis.sadd(key, *channel_strs)
        await self.redis.expire(key, ttl)

    async def delete_user_channels(self, user_id: str):
        key = RediKeys.user_channels(user_id)
        await self.redis.delete(key)

    async def push_event_to_stream(self, shard_id: str, event: Event):
        key = RediKeys.stream_shard(shard_id)
        data = EventCodec.to_redis(event)
        await self.redis.xadd(key, data)

    async def batch_push_events_to_streams(self, batch: dict[str, list[Event]]):
        pipe = self.redis.pipeline()
        for shard_id, events in batch.items():
            key = RediKeys.stream_shard(shard_id)
            event_data = [EventCodec.to_redis(event) for event in events]
            for data in event_data:
                pipe.xadd(key, data)

        await pipe.execute()

    async def query_user_channels_from_db(self, user_id: str) -> List[str]:
        """
        Mock function to simulate a database lookup.
        In production, replace this with your actual DB call.
        """
        # Replace with ORM call like:
        # return await db.get_user_channels(user_id)
        return ["c1a1e8c8-7abb-489f-88ec-66f5476c6a10"]  # Placeholder
