import asyncio
from typing import List

import structlog
from libs.rediskeys import RediKeys
from redis.asyncio import Redis
from src.config import config

logger = structlog.get_logger(__name__)


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
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt, exiting...")
                break
            except Exception as e:
                logger.error(
                    "Failed to connect to Redis, retries left: %s", retries, error=e
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

    async def register_consumer(self, consumer_id: str):
        await self.redis.sadd(RediKeys.event_consumers(), consumer_id)
        logger.info("Consumer %s registered", consumer_id)

    async def unregister_consumer(self, consumer_id: str):
        await self.redis.srem(RediKeys.event_consumers(), consumer_id)
        logger.info("Consumer %s unregistered", consumer_id)

    async def send_heartbeat(self, consumer_id: str, ttl: int = config.heartbeat_ttl):
        await self.redis.set(RediKeys.heartbeat(consumer_id), "alive", ex=ttl)

    async def fetch_leased_shards(self, consumer_id: str) -> List[str]:
        leases = await self.redis.hgetall(RediKeys.leases())
        return [
            stream_id.decode("utf-8") if isinstance(stream_id, bytes) else stream_id
            for stream_id, assigned_consumer in leases.items()
            if assigned_consumer.decode("utf-8") == str(consumer_id)
        ]

    async def read_stream(
        self, consumer_id: str, stream_name: str, consumer_group: str
    ):
        return await self.redis.xreadgroup(
            groupname=consumer_group,
            consumername=consumer_id,
            streams={stream_name: ">"},
            count=config.redis_xread_count,
            block=config.redis_xread_block,
        )

    async def get_grpc_endpoints_for_channel(self, channel_id: str) -> List[str]:
        key = RediKeys.channel_grpc_endpoints(channel_id)
        members = await self.redis.smembers(key)
        decoded_members = [m.decode() for m in members]
        logger.info(
            "Fetched instances for channel: %s, instances: %s",
            channel_id,
            decoded_members,
        )
        return decoded_members

    async def get_grpc_endpoint_for_user(self, user_id: str) -> str:
        endpoint = await self.redis.get(RediKeys.user_grpc_endpoint(user_id))
        if endpoint:
            return [endpoint.decode()]
        return None

    async def batch_ack_messages(
        self, stream_name: str, consumer_group: str, message_ids: List[str]
    ):
        """Batch acknowledge multiple messages."""
        pipe = self.redis.pipeline()
        for message_id in message_ids:
            pipe.xack(stream_name, consumer_group, message_id)
        await pipe.execute()
