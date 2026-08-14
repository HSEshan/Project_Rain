import hashlib
from typing import Iterable

import structlog
from redis.asyncio import Redis

from libs.rediskeys import RediKeys

from .codec import EventCodec
from .schema import Event

logger = structlog.get_logger()

DEFAULT_NUM_SHARDS = 16


def compute_shard_id(receiver_id: str, num_shards: int = DEFAULT_NUM_SHARDS) -> str:
    """Pick the stream shard for a receiver.

    Sharding by receiver keeps every event for one channel (or user) on one
    stream, so a single consumer sees them in order.
    """
    hash_val = int(hashlib.sha256(str(receiver_id).encode()).hexdigest(), 16)
    return str(hash_val % num_shards)


class EventPublisher:
    """Writes events onto the sharded Redis streams that event_consumer reads.

    Every producer goes through this — ws_gateway for client-sent messages,
    rest_api for mutations that clients need to hear about — so the shard
    function has exactly one implementation. `num_shards` must equal the
    consumer/lease manager's NUM_STREAMS or events land on unread shards.
    """

    def __init__(self, redis: Redis, num_shards: int = DEFAULT_NUM_SHARDS):
        self.redis = redis
        self.num_shards = num_shards

    def shard_for(self, receiver_id: str) -> str:
        return compute_shard_id(receiver_id, self.num_shards)

    async def publish(self, event: Event) -> None:
        key = RediKeys.stream_shard(self.shard_for(event.receiver_id))
        await self.redis.xadd(key, EventCodec.to_redis(event))
        logger.debug(
            "Published event", event_type=event.event_type, receiver_id=event.receiver_id
        )

    async def publish_many(self, events: Iterable[Event]) -> None:
        pipe = self.redis.pipeline()
        count = 0
        for event in events:
            key = RediKeys.stream_shard(self.shard_for(event.receiver_id))
            pipe.xadd(key, EventCodec.to_redis(event))
            count += 1
        if count:
            await pipe.execute()
            logger.debug("Published event batch", count=count)
