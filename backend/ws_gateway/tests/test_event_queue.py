"""The gateway's batch accumulator: nothing lost, nothing unbounded.

Recreates the Phase 11 harness (2026-08-24), which lived in a session scratch
directory and was lost. Two of the five silent-loss bugs fixed that day were in
this file:

- the accumulator was dispatched as a copy and *cleared afterwards*, so anything
  a client sent during the dispatch was wiped without ever being dispatched;
- it was unbounded, so a stalled Postgres let the process grow until it died.

The dispatcher here is a fake that records what it was given and can be made
slow, blocked, or failing. No database, no Redis.

    cd backend/ws_gateway && python -m unittest discover -s tests
"""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.event.schema import Event, EventType  # noqa: E402
from src.core.config import settings  # noqa: E402
from src.event import event_queue as event_queue_module  # noqa: E402
from src.event.event_queue import EventQueue  # noqa: E402

CHANNEL = str(uuid4())
SENDER = str(uuid4())


def message(n: int) -> Event:
    return Event(
        event_type=EventType.MESSAGE,
        sender_id=SENDER,
        receiver_id=CHANNEL,
        text=str(n),
    )


class RecordingDispatcher:
    """Stands in for MessageEventDispatcher. Records every event it is handed."""

    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.dispatched: list[str] = []
        self.in_flight = False
        self.calls = 0
        self.fail_first = False
        self.gate: asyncio.Event | None = None

    async def dispatch_events(self, batch):
        self.calls += 1
        self.in_flight = True
        try:
            if self.gate is not None:
                await self.gate.wait()
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.fail_first and self.calls == 1:
                raise RuntimeError("simulated Postgres failure")
            for events in batch.values():
                self.dispatched.extend(event.text for event in events)
        finally:
            self.in_flight = False


class QueueTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # A 1ms interval and a dispatch slower than it, which is production's
        # shape: a Postgres round trip is far longer than the batch interval.
        self.patches = [
            mock.patch.object(settings, "BATCH_INTERVAL_MS", 1),
            mock.patch.object(settings, "BATCH_SIZE", 50),
            mock.patch.object(settings, "MAX_PENDING_EVENTS", 10_000),
        ]
        for patch in self.patches:
            patch.start()
        self.queue = EventQueue()

    async def asyncTearDown(self):
        await self.queue.stop_batch_processor()
        for patch in reversed(self.patches):
            patch.stop()

    async def start(self, dispatcher):
        self.queue.set_event_dispatcher(dispatcher)
        await self.queue.start_batch_processor()

    async def drain(self, dispatcher, expected: int, timeout: float = 5.0):
        async with asyncio.timeout(timeout):
            while len(dispatcher.dispatched) < expected or dispatcher.in_flight:
                await asyncio.sleep(0.005)


class NothingIsLost(QueueTest):
    async def test_events_sent_during_a_dispatch_are_dispatched(self):
        dispatcher = RecordingDispatcher(delay=0.003)
        await self.start(dispatcher)

        sent_during_dispatch = 0
        for n in range(300):
            if dispatcher.in_flight:
                sent_during_dispatch += 1
            await self.queue.enqueue_event(message(n))
            await asyncio.sleep(0.001)

        await self.drain(dispatcher, 300)

        # The precondition the old bug needed. Without it this test proves nothing.
        self.assertGreater(sent_during_dispatch, 0)
        self.assertEqual(sorted(dispatcher.dispatched, key=int), [str(n) for n in range(300)])

    async def test_order_is_kept_within_the_gateway(self):
        dispatcher = RecordingDispatcher(delay=0.002)
        await self.start(dispatcher)

        for n in range(100):
            await self.queue.enqueue_event(message(n))
            await asyncio.sleep(0.0005)
        await self.drain(dispatcher, 100)

        self.assertEqual(dispatcher.dispatched, [str(n) for n in range(100)])

    async def test_the_loop_survives_a_failed_batch(self):
        dispatcher = RecordingDispatcher()
        dispatcher.fail_first = True
        await self.start(dispatcher)

        await self.queue.enqueue_event(message(0))
        async with asyncio.timeout(2):
            while dispatcher.calls < 1:
                await asyncio.sleep(0.005)

        await self.queue.enqueue_event(message(1))
        await self.drain(dispatcher, 1)

        # The failed batch is the dispatcher's to handle (it rolls back and drops
        # what it could not store); what matters here is that the next one runs.
        self.assertEqual(dispatcher.dispatched, ["1"])


class Backpressure(QueueTest):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.limit = mock.patch.object(settings, "MAX_PENDING_EVENTS", 5)
        self.limit.start()
        self.timeout = mock.patch.object(
            event_queue_module, "BACKPRESSURE_TIMEOUT_SECONDS", 0.3
        )
        self.timeout.start()

    async def asyncTearDown(self):
        self.timeout.stop()
        self.limit.stop()
        await super().asyncTearDown()

    async def wedge(self):
        """Start the loop, let it take one batch, and block it inside the dispatch."""
        dispatcher = RecordingDispatcher()
        dispatcher.gate = asyncio.Event()
        await self.start(dispatcher)
        await self.queue.enqueue_event(message(-1))
        async with asyncio.timeout(2):
            while not dispatcher.in_flight:
                await asyncio.sleep(0.005)
        return dispatcher

    async def test_the_buffer_never_grows_past_its_limit(self):
        await self.wedge()
        for n in range(5):
            await self.queue.enqueue_event(message(n))

        with self.assertRaises(RuntimeError):
            await self.queue.enqueue_event(message(5))
        self.assertEqual(self.queue.batch_size, 5)

    async def test_a_waiting_producer_goes_through_once_it_drains(self):
        dispatcher = await self.wedge()
        for n in range(5):
            await self.queue.enqueue_event(message(n))

        waiting = asyncio.create_task(self.queue.enqueue_event(message(5)))
        await asyncio.sleep(0.05)
        self.assertFalse(waiting.done(), "a full buffer must make the producer wait")

        dispatcher.gate.set()
        await asyncio.wait_for(waiting, timeout=1)
        await self.drain(dispatcher, 7)

        self.assertEqual(sorted(dispatcher.dispatched, key=int), [str(n) for n in range(-1, 6)])


if __name__ == "__main__":
    unittest.main()
