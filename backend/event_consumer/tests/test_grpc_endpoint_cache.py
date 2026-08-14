"""Endpoint cache policy.

Stdlib `unittest` on purpose: this image has no pytest and does not need one.

    docker compose run --rm --no-deps event_consumer python -m unittest discover -s tests

The rule under test cost us a real bug. The consumer caches which gateways hold
a channel's members for 30 seconds. Caching the *empty* answer meant that one
client refreshing — a moment when nobody is connected — made the channel
undeliverable for the rest of the window, long after the gateway had
re-registered itself. Messages and voice presence were published, routed, and
silently dropped.
"""

import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.grpc_endpoint_cache import GrpcEndpointCache  # noqa: E402


class FakeRedisManager:
    """Returns the next queued answer and counts how often it was asked."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = 0

    async def get_grpc_endpoints_for_channel(self, receiver_id):
        self.calls += 1
        return self.answers.pop(0) if self.answers else []

    async def get_grpc_endpoint_for_user(self, receiver_id):
        return await self.get_grpc_endpoints_for_channel(receiver_id)


class GrpcEndpointCacheTest(unittest.TestCase):
    def setUp(self):
        self.cache = GrpcEndpointCache()

    def lookup(self, channel="channel-1", event_type="message"):
        return asyncio.run(self.cache.get_cached_endpoints(channel, event_type))

    def test_reuses_a_known_endpoint(self):
        self.cache.redis_manager = FakeRedisManager([["ws_gateway:6000"]])

        self.assertEqual(self.lookup(), ["ws_gateway:6000"])
        self.assertEqual(self.lookup(), ["ws_gateway:6000"])
        self.assertEqual(
            self.cache.redis_manager.calls, 1, "a known endpoint should be cached"
        )

    def test_does_not_cache_nobody_connected(self):
        # Empty, then the client reconnects and the gateway re-registers
        self.cache.redis_manager = FakeRedisManager([[], ["ws_gateway:6000"]])

        self.assertEqual(self.lookup(), [])
        self.assertEqual(
            self.lookup(),
            ["ws_gateway:6000"],
            "an empty result must not be cached, or a reconnecting client stays "
            "unreachable until the TTL expires",
        )
        self.assertEqual(self.cache.redis_manager.calls, 2)

    def test_an_empty_result_evicts_a_stale_entry(self):
        self.cache.redis_manager = FakeRedisManager([["ws_gateway:6000"], [], []])

        self.assertEqual(self.lookup(), ["ws_gateway:6000"])
        self.assertEqual(self.lookup(), ["ws_gateway:6000"], "served from cache")
        # Expire it so the next call goes to Redis and comes back empty
        self.cache.cache_ttl = 0
        self.assertEqual(self.lookup(), [])

        self.cache.cache_ttl = 30
        self.assertEqual(self.lookup(), [], "the stale entry must be gone")
        self.assertEqual(self.cache.redis_manager.calls, 3)

    def test_channel_and_user_addressing_do_not_share_an_entry(self):
        # `receiver_id` means a channel for some event types and a user for
        # others; the cache key has to keep them apart
        self.cache.redis_manager = FakeRedisManager(
            [["gateway-a:6000"], ["gateway-b:6000"]]
        )

        self.assertEqual(self.lookup("id-1", "message"), ["gateway-a:6000"])
        self.assertEqual(self.lookup("id-1", "notification"), ["gateway-b:6000"])


if __name__ == "__main__":
    unittest.main()
