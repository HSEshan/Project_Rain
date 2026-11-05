"""The rate limiter's decisions, without a Redis.

The script itself runs against a real Redis in `tests/e2e/rate_limit_probe.py`.
These pin down what is decided from its answer, including the failure direction,
which is the part most worth not changing by accident.
"""

import unittest

from libs.rate_limit import RateLimit, hit
from redis.exceptions import ConnectionError as RedisConnectionError

RULE = RateLimit("test", limit=2, window_seconds=60)


class FakeRedis:
    """Counts per key, the way the script does."""

    def __init__(self, ttl=42):
        self.counts = {}
        self.ttl = ttl

    async def eval(self, script, numkeys, key, window):
        self.counts[key] = self.counts.get(key, 0) + 1
        return [self.counts[key], self.ttl]


class BrokenRedis:
    async def eval(self, *args):
        raise RedisConnectionError("gone")


class HitTest(unittest.IsolatedAsyncioTestCase):
    async def test_allows_up_to_the_limit_and_refuses_after(self):
        redis = FakeRedis()
        self.assertTrue((await hit(redis, RULE, "a")).allowed)
        self.assertTrue((await hit(redis, RULE, "a")).allowed)
        self.assertFalse((await hit(redis, RULE, "a")).allowed)

    async def test_a_refusal_says_how_long_to_wait(self):
        redis = FakeRedis(ttl=42)
        await hit(redis, RULE, "a")
        await hit(redis, RULE, "a")
        self.assertEqual((await hit(redis, RULE, "a")).retry_after, 42)

    async def test_retry_after_is_never_zero(self):
        # TTL can read 0 in a window's last moments, and "retry in 0 seconds" is
        # an invitation to spin.
        redis = FakeRedis(ttl=0)
        await hit(redis, RULE, "a")
        await hit(redis, RULE, "a")
        self.assertEqual((await hit(redis, RULE, "a")).retry_after, 1)

    async def test_identities_do_not_share_a_counter(self):
        redis = FakeRedis()
        await hit(redis, RULE, "a")
        await hit(redis, RULE, "a")
        await hit(redis, RULE, "a")
        self.assertTrue((await hit(redis, RULE, "b")).allowed)

    async def test_rules_do_not_share_a_counter(self):
        redis = FakeRedis()
        other = RateLimit("other", limit=2, window_seconds=60)
        await hit(redis, RULE, "a")
        await hit(redis, RULE, "a")
        await hit(redis, RULE, "a")
        self.assertTrue((await hit(redis, other, "a")).allowed)

    async def test_a_redis_failure_allows_the_request(self):
        self.assertTrue((await hit(BrokenRedis(), RULE, "a")).allowed)

    async def test_no_redis_allows_the_request(self):
        self.assertTrue((await hit(None, RULE, "a")).allowed)


if __name__ == "__main__":
    unittest.main()
