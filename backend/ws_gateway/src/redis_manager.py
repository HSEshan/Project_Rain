import asyncio
from typing import List, Optional

import structlog
from src.core.config import settings
from redis.asyncio import Redis

from libs.event.codec import EventCodec
from libs.event.schema import Event

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
            raise Exception("Failed to connect to Redis, max retries reached")

    async def disconnect(self):
        if self.redis:
            await self.redis.aclose()
        logger.info("Disconnected from Redis")

    async def set_user_instance(
        self, user_id: str, grpc_endpoint: str, ttl: int = settings.DEFAULT_TTL_SECONDS
    ):
        await self.redis.setex(f"user:{user_id}:instance", ttl, grpc_endpoint)

    async def get_user_instance(self, user_id: str) -> Optional[str]:
        return await self.redis.get(f"user:{user_id}:instance")

    async def delete_user_instance(self, user_id: str):
        await self.redis.delete(f"user:{user_id}:instance")

    async def add_instance_to_channel(
        self,
        channel_id: str,
        grpc_endpoint: str,
        ttl: int = settings.DEFAULT_TTL_SECONDS,
    ):
        key = f"channel:{channel_id}:instances"
        await self.redis.sadd(key, grpc_endpoint)
        await self.redis.expire(key, ttl)

    async def remove_instance_from_channel(self, channel_id: str, grpc_endpoint: str):
        key = f"channel:{channel_id}:instances"
        await self.redis.srem(key, grpc_endpoint)
        if await self.redis.scard(key) == 0:
            await self.redis.delete(key)

    async def add_channel_to_user(
        self, user_id: str, channel_id: str, ttl: int = settings.DEFAULT_TTL_SECONDS
    ):
        key = f"user:{user_id}:channels"
        await self.redis.sadd(key, str(channel_id))
        await self.redis.expire(key, ttl)

    async def remove_channel_from_user(self, user_id: str, channel_id: str):
        key = f"user:{user_id}:channels"
        await self.redis.srem(key, str(channel_id))
        if await self.redis.scard(key) == 0:
            await self.redis.delete(key)

    async def get_user_channel_ids(self, user_id: str) -> List[str]:
        key = f"user:{user_id}:channels"
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
        ttl: int = settings.DEFAULT_TTL_SECONDS,
    ):
        key = f"user:{user_id}:channels"
        channel_strs = [str(cid) for cid in channel_ids]
        await self.redis.sadd(key, *channel_strs)
        await self.redis.expire(key, ttl)

    async def delete_user_channels(self, user_id: str):
        key = f"user:{user_id}:channels"
        await self.redis.delete(key)

    async def push_event_to_stream(self, shard_id: str, event: Event):
        key = f"stream:{shard_id}"
        data = EventCodec.pydantic_to_redis(event)
        await self.redis.xadd(key, data)

    async def query_user_channels_from_db(self, user_id: str) -> List[str]:
        """
        Mock function to simulate a database lookup.
        In production, replace this with your actual DB call.
        """
        # Replace with ORM call like:
        # return await db.get_user_channels(user_id)
        return [
            "c641e03c-2571-4479-abbc-8d7143913457",
            "e7dfa25a-fb72-44ca-b5fc-632d954ef93c",
        ]  # Placeholder
