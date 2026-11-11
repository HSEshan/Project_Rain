"""A crashed gateway is pruned from its routes; a slow live one is not.

    docker compose run --rm --no-deps event_consumer python -m unittest discover -s tests

Measured 2026-11-11 with two replicas: after one was SIGKILLed it stayed in
every channel set it had joined, the first message to those channels waited the
full GRPC_TIMEOUT (5s), and every later batch for them failed. The rule under
test: prune only when the delivery failed *and* the gateway's heartbeat is gone.
"""

import json
import sys
import time
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.stream_worker import StreamWorker  # noqa: E402

LIVE, DEAD = "live:6000", "dead:6000"
CHANNEL, USER = str(uuid4()), str(uuid4())


def entry(target_type: str, target_id: str, text: str):
    fields = {
        "event_id": str(uuid4()),
        "event_type": "message" if target_type == "channel" else "notification",
        "sender_id": str(uuid4()),
        "receiver_id": target_id,
        "target_type": target_type,
        "target_id": target_id,
        "text": text,
        "metadata": json.dumps({}),
        "timestamp": "2026-11-11T12:00:00+00:00",
    }
    stamp = int(time.time() * 1000)
    return (f"{stamp}-0".encode(), {k.encode(): v.encode() for k, v in fields.items()})


class FakeRedis:
    def __init__(self, alive: set[str]):
        self.alive = alive
        self.pruned: list[tuple[str, list[str], list[str]]] = []
        self.acked: list[bytes] = []

    async def gateway_alive(self, endpoint):
        return endpoint in self.alive

    async def prune_endpoint(self, endpoint, channel_ids, user_ids):
        self.pruned.append((endpoint, channel_ids, user_ids))

    async def batch_ack_messages(self, stream, group, message_ids):
        self.acked.extend(message_ids)


class FakeCache:
    def __init__(self):
        self.forgotten: list[str] = []

    async def get_cached_endpoints(self, target_id, target_type):
        return [LIVE, DEAD]

    def forget_endpoint(self, endpoint):
        self.forgotten.append(endpoint)


class Stub:
    def __init__(self, endpoint, delivered):
        self.endpoint, self.delivered = endpoint, delivered

    async def SendEvents(self, batch, timeout=None):
        if self.endpoint == DEAD:
            raise ConnectionError("unreachable")
        self.delivered.extend(event.text for event in batch.events)


class Pool:
    def __init__(self):
        self.delivered: list[str] = []

    async def get_stub(self, endpoint):
        return Stub(endpoint, self.delivered)


class DeadGateway(unittest.IsolatedAsyncioTestCase):
    async def run_batch(self, alive):
        redis, cache, pool = FakeRedis(alive), FakeCache(), Pool()
        worker = StreamWorker("stream_shard:0", "c1", pool, cache, redis)
        batch = [
            entry("channel", CHANNEL, "to the channel"),
            entry("user", USER, "to the user"),
        ]
        await worker._process_batch([(b"stream_shard:0", batch)])
        return redis, cache, pool, batch

    async def test_a_dead_gateway_is_pruned_from_the_routes_that_led_to_it(self):
        redis, cache, pool, _ = await self.run_batch(alive={LIVE})

        self.assertEqual(redis.pruned, [(DEAD, [CHANNEL], [USER])])
        self.assertEqual(cache.forgotten, [DEAD])

    async def test_a_live_gateway_that_failed_once_keeps_its_routes(self):
        """Slow, not gone: its heartbeat is fresh, so nothing is removed."""
        redis, cache, _, _ = await self.run_batch(alive={LIVE, DEAD})

        self.assertEqual(redis.pruned, [])
        self.assertEqual(cache.forgotten, [DEAD])

    async def test_the_live_gateway_still_gets_everything_and_the_batch_is_acked(self):
        redis, _, pool, batch = await self.run_batch(alive={LIVE})

        self.assertEqual(sorted(pool.delivered), ["to the channel", "to the user"])
        self.assertEqual(redis.acked, [message_id for message_id, _ in batch])

    async def test_a_failure_while_pruning_does_not_cost_the_ack(self):
        redis = FakeRedis(alive={LIVE})

        async def broken(*args):
            raise ConnectionError("redis blip")

        redis.prune_endpoint = broken
        worker = StreamWorker("stream_shard:0", "c1", Pool(), FakeCache(), redis)
        batch = [entry("channel", CHANNEL, "x")]

        await worker._process_batch([(b"stream_shard:0", batch)])

        self.assertEqual(redis.acked, [batch[0][0]])


if __name__ == "__main__":
    unittest.main()
