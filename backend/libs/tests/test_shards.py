"""Tests for the shard count: resolution order and the agreement check.

Stdlib `unittest`, like `event_consumer/tests`, so it runs without pytest:

    cd backend/libs && python -m unittest discover -s tests
"""

import unittest

from structlog.testing import capture_logs

from libs.event.shards import (
    DEFAULT_NUM_SHARDS,
    LEGACY_SHARD_COUNT_ENV,
    SHARD_COUNT_ENV,
    register_shard_count,
    resolve_shard_count,
)


class ResolveShardCount(unittest.TestCase):
    def test_canonical_name_wins_over_the_legacy_one(self):
        count, source = resolve_shard_count(
            {SHARD_COUNT_ENV: "4", LEGACY_SHARD_COUNT_ENV: "2"}
        )
        self.assertEqual(count, 4)
        self.assertEqual(source, SHARD_COUNT_ENV)

    def test_legacy_name_still_works_and_says_so(self):
        """The whole point of the migration: an old env file keeps booting."""
        with capture_logs() as logs:
            count, source = resolve_shard_count({LEGACY_SHARD_COUNT_ENV: "2"})
        self.assertEqual(count, 2)
        self.assertEqual(source, LEGACY_SHARD_COUNT_ENV)
        self.assertEqual([entry["log_level"] for entry in logs], ["warning"])

    def test_blank_value_is_not_a_value(self):
        count, _ = resolve_shard_count(
            {SHARD_COUNT_ENV: "  ", LEGACY_SHARD_COUNT_ENV: "2"}
        )
        self.assertEqual(count, 2)

    def test_falls_back_to_the_default(self):
        count, source = resolve_shard_count({})
        self.assertEqual(count, DEFAULT_NUM_SHARDS)
        self.assertEqual(source, "default")

    def test_no_default_means_required(self):
        with self.assertRaises(ValueError):
            resolve_shard_count({}, default=None)

    def test_rejects_a_non_integer(self):
        with self.assertRaises(ValueError):
            resolve_shard_count({SHARD_COUNT_ENV: "two"})

    def test_rejects_zero(self):
        """`hash % 0` is a ZeroDivisionError on every publish."""
        with self.assertRaises(ValueError):
            resolve_shard_count({SHARD_COUNT_ENV: "0"})


class FakeRedis:
    """Enough of the Redis interface for the agreement check, bytes and all."""

    def __init__(self, existing=None, fail=False):
        self.hash = dict(existing or {})
        self.fail = fail
        self.expired = None

    async def hset(self, key, field, value):
        if self.fail:
            raise ConnectionError("redis is down")
        self.hash[field] = value

    async def expire(self, key, ttl):
        self.expired = ttl

    async def hgetall(self, key):
        return {k.encode(): str(v).encode() for k, v in self.hash.items()}


class RegisterShardCount(unittest.IsolatedAsyncioTestCase):
    async def test_records_this_service_and_reads_the_others(self):
        redis = FakeRedis({"lease_manager": 2})
        reported = await register_shard_count(redis, "rest_api", 2)
        self.assertEqual(reported, {"lease_manager": 2, "rest_api": 2})
        self.assertIsNotNone(redis.expired)

    async def test_reports_a_disagreement(self):
        """The production failure mode: rest_api on 16, everyone else on 2."""
        redis = FakeRedis({"lease_manager": 2, "ws_gateway": 2})
        with capture_logs() as logs:
            reported = await register_shard_count(redis, "rest_api", 16)
        self.assertEqual(reported["rest_api"], 16)
        self.assertTrue(any(entry["log_level"] == "error" for entry in logs))

    async def test_a_redis_failure_does_not_stop_the_service(self):
        reported = await register_shard_count(FakeRedis(fail=True), "rest_api", 2)
        self.assertEqual(reported, {})


if __name__ == "__main__":
    unittest.main()
