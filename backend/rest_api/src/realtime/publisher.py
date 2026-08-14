from typing import Iterable

import structlog
from libs.event.publisher import EventPublisher
from libs.event.schema import Event
from libs.rediskeys import RediKeys
from redis.asyncio import Redis
from src.core.config import settings

logger = structlog.get_logger()


class RealtimePublisher:
    """How rest_api tells connected clients that something changed.

    REST owns the database; the websocket gateway owns sockets. Rather than
    calling a specific gateway (there may be several), rest_api writes onto the
    same Redis streams the gateway writes to, and event_consumer routes each
    event to whichever gateway holds the recipient.

    Publishing is best-effort by design: the transaction has already committed
    by the time we get here, so a Redis outage must not turn a successful
    mutation into a 500. Clients still converge on their next fetch.
    """

    def __init__(self):
        self.redis: Redis | None = None
        self.publisher: EventPublisher | None = None

    async def connect(self):
        try:
            self.redis = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
            )
            await self.redis.ping()
            self.publisher = EventPublisher(self.redis, settings.NUM_SHARDS)
            logger.info("Realtime publisher connected to Redis")
        except Exception:
            logger.exception("Realtime publisher could not reach Redis")
            self.redis = None
            self.publisher = None

    async def disconnect(self):
        if self.redis:
            await self.redis.aclose()
            self.redis = None
            self.publisher = None

    async def publish(self, *events: Event):
        await self.publish_many(events)

    async def publish_many(self, events: Iterable[Event]):
        events = [event for event in events if event is not None]
        if not events:
            return
        if not self.publisher:
            logger.warning("Realtime publisher unavailable, dropping events")
            return
        try:
            await self.publisher.publish_many(events)
        except Exception:
            logger.exception("Failed to publish events")

    async def invalidate_user_channels(self, *user_ids: str):
        """Drop the gateway's cached membership for these users.

        The gateway caches `user:{id}:channels` for 120s. rest_api is the writer
        of that membership, so it clears the cache; connected users additionally
        get a CHANNELS_CHANGED event so their gateway re-reads immediately.
        """
        if not self.redis or not user_ids:
            return
        try:
            await self.redis.delete(
                *[RediKeys.user_channels(str(user_id)) for user_id in user_ids]
            )
        except Exception:
            logger.exception("Failed to invalidate user channel cache")


realtime_publisher = RealtimePublisher()
