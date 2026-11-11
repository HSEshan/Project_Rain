import asyncio
from typing import List

import structlog
from libs.rediskeys import RediKeys
from redis.asyncio import Redis
from src.config import config

logger = structlog.get_logger(__name__)

# Compare-and-delete in one round trip, so a GET then DEL cannot remove a value
# another gateway wrote in between.
_DELETE_IF_EQUAL = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


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
                    "Failed to connect to Redis, retries left", retries=retries, error=e
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
        logger.info("Consumer registered", consumer_id=consumer_id)

    async def unregister_consumer(self, consumer_id: str):
        await self.redis.srem(RediKeys.event_consumers(), consumer_id)
        logger.info("Consumer unregistered", consumer_id=consumer_id)

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
            "Fetched instances for channel",
            channel_id=channel_id,
            instances=decoded_members,
        )

        return decoded_members

    async def get_grpc_endpoint_for_user(self, user_id: str) -> str:
        endpoint = await self.redis.get(RediKeys.user_grpc_endpoint(user_id))
        if endpoint:
            return [endpoint.decode()]
        return None

    async def autoclaim(
        self,
        stream_name: str,
        consumer_group: str,
        consumer_id: str,
        min_idle_ms: int,
        start_id: str | bytes,
        count: int,
    ):
        """XAUTOCLAIM: take over entries pending longer than `min_idle_ms`.

        Returns `(next_start_id, claimed_messages)`. Redis 7 also returns the ids
        of entries that were trimmed out of the stream while pending; it removes
        those from the pending list itself, so there is nothing to do with them.
        """
        result = await self.redis.xautoclaim(
            stream_name,
            consumer_group,
            consumer_id,
            min_idle_time=min_idle_ms,
            start_id=start_id,
            count=count,
        )
        return result[0], result[1]

    async def server_time_ms(self) -> int:
        seconds, microseconds = await self.redis.time()
        return int(seconds) * 1000 + int(microseconds) // 1000

    async def gateway_alive(self, grpc_endpoint: str) -> bool:
        return bool(await self.redis.exists(RediKeys.gateway_heartbeat(grpc_endpoint)))

    async def prune_endpoint(
        self, grpc_endpoint: str, channel_ids: list[str], user_ids: list[str]
    ) -> None:
        """Remove a dead gateway from the routes it was found in.

        Channel sets lose the member. A user key is deleted only if it still
        names this endpoint: the user may already have reconnected to a live
        gateway, which overwrote it, and that route must survive.
        """
        pipe = self.redis.pipeline(transaction=False)
        for channel_id in channel_ids:
            pipe.srem(RediKeys.channel_grpc_endpoints(channel_id), grpc_endpoint)
        for user_id in user_ids:
            pipe.eval(
                _DELETE_IF_EQUAL,
                1,
                RediKeys.user_grpc_endpoint(user_id),
                grpc_endpoint,
            )
        await pipe.execute()

    async def batch_ack_messages(
        self, stream_name: str, consumer_group: str, message_ids: List[str]
    ):
        """Batch acknowledge multiple messages."""
        pipe = self.redis.pipeline()
        for message_id in message_ids:
            pipe.xack(stream_name, consumer_group, message_id)
        await pipe.execute()
