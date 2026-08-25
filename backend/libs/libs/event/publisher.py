import hashlib
from typing import Iterable

import structlog
from redis.asyncio import Redis

from libs.rediskeys import RediKeys

from .codec import EventCodec
from .schema import Event

logger = structlog.get_logger()

DEFAULT_NUM_SHARDS = 16

# How many entries a shard keeps. XACK removes an entry from a consumer group's
# pending list, it does **not** remove it from the stream: a stream is
# append-only and only shrinks when it is trimmed. Without this every shard grew
# in Redis memory for the life of the deployment.
#
# This is the real number to think about: it is how far a consumer may fall
# behind before undelivered events are discarded to make room. At this
# workload's volume 10k entries per shard is hours of headroom, and 16 shards of
# 10k small entries is on the order of tens of megabytes.
DEFAULT_STREAM_MAXLEN = 10_000


def compute_shard_id(target_id: str, num_shards: int = DEFAULT_NUM_SHARDS) -> str:
    """Pick the stream shard for a target.

    Sharding by target keeps every event for one channel (or user) on one
    stream, so a single consumer sees them in order.
    """
    hash_val = int(hashlib.sha256(str(target_id).encode()).hexdigest(), 16)
    return str(hash_val % num_shards)


class EventPublisher:
    """Writes events onto the sharded Redis streams that event_consumer reads.

    Every producer goes through this — ws_gateway for client-sent messages,
    rest_api for mutations that clients need to hear about — so the shard
    function has exactly one implementation. `num_shards` must equal the
    consumer/lease manager's NUM_STREAMS or events land on unread shards.
    """

    def __init__(
        self,
        redis: Redis,
        num_shards: int = DEFAULT_NUM_SHARDS,
        maxlen: int = DEFAULT_STREAM_MAXLEN,
    ):
        self.redis = redis
        self.num_shards = num_shards
        self.maxlen = maxlen

    def shard_for(self, target_id: str) -> str:
        return compute_shard_id(target_id, self.num_shards)

    async def publish(self, event: Event) -> None:
        key = RediKeys.stream_shard(self.shard_for(event.target_id))
        await self.redis.xadd(key, EventCodec.to_redis(event), **self._trim())
        logger.debug(
            "Published event",
            event_type=event.event_type,
            target_type=event.target_type,
            target_id=event.target_id,
        )

    async def publish_many(self, events: Iterable[Event]) -> None:
        pipe = self.redis.pipeline()
        count = 0
        trim = self._trim()
        for event in events:
            key = RediKeys.stream_shard(self.shard_for(event.target_id))
            pipe.xadd(key, EventCodec.to_redis(event), **trim)
            count += 1
        if count:
            await pipe.execute()
            logger.debug("Published event batch", count=count)

    def _trim(self) -> dict:
        """Trim arguments for XADD, or nothing when trimming is disabled.

        `approximate=True` is the important part: it lets Redis trim on whole
        radix tree nodes rather than walking to an exact length, which is O(1)
        amortised instead of a cost paid on every single write. The stream then
        sits somewhere near `maxlen` rather than exactly on it, which is fine
        for a bound whose job is to stop unbounded growth.
        """
        if not self.maxlen:
            return {}
        return {"maxlen": self.maxlen, "approximate": True}
