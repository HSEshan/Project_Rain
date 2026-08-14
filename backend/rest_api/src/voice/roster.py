"""Who is currently in each voice channel.

**LiveKit is the source of truth and the only writer.** rest_api used to add and
remove entries around its own join/leave endpoints, which meant a browser that
refreshed, crashed, or was killed left a ghost in the list forever — and joining
a second channel then showed the user in both. The SFU already knows exactly who
is connected, so it tells us: `participant_joined` / `participant_left` /
`room_started` webhooks drive this set (see `routes.py`).

The set is still a cache rather than a query, because it has to be readable by
someone who has *not* joined the room — that is the whole point of showing a
roster under a channel in the sidebar.
"""

import structlog
from libs.rediskeys import RediKeys

from src.realtime.publisher import RealtimePublisher, realtime_publisher

logger = structlog.get_logger()


class VoiceRoster:
    def __init__(self, publisher: RealtimePublisher):
        # Shares the publisher's connection rather than opening a second one;
        # it has the same "Redis is down, degrade quietly" contract.
        self._publisher = publisher

    @property
    def _redis(self):
        return self._publisher.redis

    async def add(self, channel_id: str, user_id: str) -> None:
        if not self._redis:
            return
        try:
            await self._redis.sadd(RediKeys.channel_voice_members(channel_id), user_id)
        except Exception:
            logger.exception("Failed to add voice member", channel_id=channel_id)

    async def remove(self, channel_id: str, user_id: str) -> None:
        if not self._redis:
            return
        key = RediKeys.channel_voice_members(channel_id)
        try:
            await self._redis.srem(key, user_id)
            if await self._redis.scard(key) == 0:
                await self._redis.delete(key)
        except Exception:
            logger.exception("Failed to remove voice member", channel_id=channel_id)

    async def clear(self, channel_id: str) -> list[str]:
        """Empty the roster, returning who was in it.

        Called when LiveKit starts or finishes a room. `room_started` means the
        SFU believes nobody is in there, so anything we still hold is stale —
        this is what heals a roster that ghosted before webhooks existed.
        """
        if not self._redis:
            return []
        members = await self.members(channel_id)
        try:
            await self._redis.delete(RediKeys.channel_voice_members(channel_id))
        except Exception:
            logger.exception("Failed to clear voice members", channel_id=channel_id)
        return members

    async def members(self, channel_id: str) -> list[str]:
        if not self._redis:
            return []
        try:
            raw = await self._redis.smembers(
                RediKeys.channel_voice_members(channel_id)
            )
        except Exception:
            logger.exception("Failed to read voice members", channel_id=channel_id)
            return []
        return sorted(member.decode() for member in raw)


voice_roster = VoiceRoster(realtime_publisher)
