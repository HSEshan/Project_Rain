"""The reclaim pass: stranded entries are delivered, or dropped once too old.

    docker compose run --rm --no-deps event_consumer python -m unittest discover -s tests

Stranded means read and never acknowledged: a consumer died mid-batch, or its
shard moved and its worker was cancelled mid-batch. Reads use ">", so before
this nothing would look at them again. Fakes stand in for Redis, the endpoint
cache and the gRPC pool; what is under test is the policy, not redis-py.
"""

import asyncio
import json
import sys
import time
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import stream_worker  # noqa: E402
from src.stream_worker import StreamWorker  # noqa: E402

STREAM = "stream_shard:0"
GATEWAY = "gateway-1:6000"


def entry(age_ms: int, text: str = "hi", event_type: str = "message"):
    """A raw stream entry as redis-py returns it, `age_ms` old."""
    stamp = int(time.time() * 1000) - age_ms
    fields = {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "sender_id": str(uuid4()),
        "receiver_id": str(uuid4()),
        "target_type": "channel",
        "target_id": str(uuid4()),
        "text": text,
        "metadata": json.dumps({}),
        "timestamp": "2026-11-11T12:00:00+00:00",
    }
    fields["receiver_id"] = fields["target_id"]
    return (f"{stamp}-0".encode(), {k.encode(): v.encode() for k, v in fields.items()})


class FakeRedis:
    def __init__(self, pages):
        # Each page: (next_start_id, claimed entries)
        self.pages = list(pages)
        self.autoclaim_calls = []
        self.acked: list[bytes] = []

    async def autoclaim(self, stream, group, consumer, min_idle_ms, start_id, count):
        self.autoclaim_calls.append((start_id, min_idle_ms))
        return self.pages.pop(0) if self.pages else (b"0-0", [])

    async def batch_ack_messages(self, stream, group, message_ids):
        self.acked.extend(message_ids)

    async def server_time_ms(self):
        return int(time.time() * 1000)


class FakeCache:
    async def get_cached_endpoints(self, target_id, target_type):
        return [GATEWAY]

    def forget_endpoint(self, endpoint):
        pass


class FakeStub:
    def __init__(self, sent):
        self.sent = sent

    async def SendEvents(self, batch, timeout=None):
        self.sent.extend(event.text for event in batch.events)


class FakePool:
    def __init__(self):
        self.sent: list[str] = []

    async def get_stub(self, endpoint):
        return FakeStub(self.sent)


class Reclaim(unittest.IsolatedAsyncioTestCase):
    async def worker(self, pages):
        redis, pool = FakeRedis(pages), FakePool()
        worker = StreamWorker(STREAM, "consumer-1", pool, FakeCache(), redis)
        return worker, redis, pool

    async def test_a_recent_stranded_entry_is_delivered_and_acked(self):
        fresh = entry(age_ms=15_000, text="late but fine")
        worker, redis, pool = await self.worker([(b"0-0", [fresh])])

        await worker._reclaim()

        self.assertEqual(pool.sent, ["late but fine"])
        self.assertEqual(redis.acked, [fresh[0]])

    async def test_an_old_stranded_entry_is_acked_and_not_delivered(self):
        """A presence event a minute late would put someone back in a room."""
        old = entry(age_ms=stream_worker.RECLAIM_MAX_AGE_MS + 5_000, text="too late")
        worker, redis, pool = await self.worker([(b"0-0", [old])])

        await worker._reclaim()

        self.assertEqual(pool.sent, [])
        self.assertEqual(redis.acked, [old[0]])

    async def test_a_mixed_page(self):
        fresh, old = entry(12_000, "fresh"), entry(120_000, "old")
        worker, redis, pool = await self.worker([(b"0-0", [old, fresh])])

        await worker._reclaim()

        self.assertEqual(pool.sent, ["fresh"])
        self.assertEqual(sorted(redis.acked), sorted([old[0], fresh[0]]))

    async def test_presence_is_never_delivered_late(self):
        """A stranded "left" arriving after a newer "joined" would empty a room."""
        presence = entry(age_ms=15_000, text="left voice", event_type="voice_state")
        edit = entry(age_ms=15_000, text="old edit", event_type="message_update")
        worker, redis, pool = await self.worker([(b"0-0", [presence, edit])])

        await worker._reclaim()

        self.assertEqual(pool.sent, [])
        self.assertEqual(sorted(redis.acked), sorted([presence[0], edit[0]]))

    async def test_pages_are_followed_and_bounded(self):
        pages = [(f"{n}-1".encode(), [entry(11_000, str(n))]) for n in range(50)]
        worker, redis, pool = await self.worker(pages)

        await worker._reclaim()

        self.assertEqual(len(redis.autoclaim_calls), stream_worker.RECLAIM_MAX_PAGES)
        self.assertEqual(redis.autoclaim_calls[1][0], b"0-1", "continues from the cursor")
        self.assertEqual(len(pool.sent), stream_worker.RECLAIM_MAX_PAGES)

    async def test_nothing_pending_costs_one_call(self):
        worker, redis, pool = await self.worker([])

        await worker._reclaim()

        self.assertEqual(len(redis.autoclaim_calls), 1)
        self.assertEqual(pool.sent, [])

    async def test_only_entries_idle_longer_than_a_healthy_batch_are_claimed(self):
        """A shard mid-handover: the other consumer may still be working on it."""
        worker, redis, _ = await self.worker([])

        await worker._reclaim()

        min_idle = redis.autoclaim_calls[0][1]
        self.assertGreaterEqual(min_idle, 10_000)
        self.assertGreater(min_idle, stream_worker.config.grpc_timeout * 1000)


class EntryAge(unittest.TestCase):
    def test_reads_the_timestamp_half_of_the_id(self):
        self.assertEqual(stream_worker.entry_age_ms(b"1000-7", 4000), 3000)
        self.assertEqual(stream_worker.entry_age_ms("1000-0", 1000), 0)



class GracefulStop(unittest.IsolatedAsyncioTestCase):
    """Moving a shard must not cut a batch between its send and its ACK."""

    async def test_stop_lets_the_batch_in_flight_finish(self):
        acked = []

        class SlowRedis(FakeRedis):
            async def read_stream(self, consumer, stream, group):
                if acked:
                    await asyncio.sleep(0.01)
                    return None
                return [(STREAM.encode(), [entry(0, "in flight")])]

            async def batch_ack_messages(self, stream, group, message_ids):
                acked.extend(message_ids)

        class SlowPool(FakePool):
            async def get_stub(self, endpoint):
                stub = FakeStub(self.sent)
                original = stub.SendEvents

                async def slow(batch, timeout=None):
                    await asyncio.sleep(0.2)
                    await original(batch, timeout)

                stub.SendEvents = slow
                return stub

        redis, pool = SlowRedis([]), SlowPool()
        worker = StreamWorker(STREAM, "consumer-1", pool, FakeCache(), redis)
        worker._next_reclaim = float("inf")
        worker.start()
        await asyncio.sleep(0.05)  # the batch is now mid-send

        await worker.stop()

        self.assertEqual(pool.sent, ["in flight"])
        self.assertEqual(len(acked), 1, "acknowledged, so nobody reclaims it")


if __name__ == "__main__":
    unittest.main()