import asyncio
from collections import defaultdict
from typing import Dict, List

import structlog
from libs.event.schema import Event
from src.core.config import settings
from src.event.event_dispatcher import EventDispatcher

logger = structlog.get_logger()

# How long a producer waits for the accumulator to drain before giving up on
# an event. Long enough to ride out a slow batch, short enough that a wedged
# gateway refuses work instead of swallowing it.
BACKPRESSURE_TIMEOUT_SECONDS = 5


class EventQueue:
    def __init__(self):
        self.batch: Dict[str, List[Event]] = defaultdict(list)
        self.batch_size = 0
        self._batch_task: asyncio.Task | None = None
        self.event_dispatcher: EventDispatcher | None = None

    def set_event_dispatcher(self, event_dispatcher: EventDispatcher):
        self.event_dispatcher = event_dispatcher

    async def start_batch_processor(self):
        self._batch_task = asyncio.create_task(self._run_batch_loop())
        logger.info("Event batch processor started")

    async def stop_batch_processor(self):
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

    async def enqueue_event(self, event: Event):
        """Accept an event for the next batch, applying backpressure when full.

        The accumulator used to be unbounded. A Redis outage costs nothing here
        (the publish is downstream), but a slow or dead Postgres stalls the
        batch loop inside its await while this keeps appending, and the process
        grows until it dies.

        Dropping is not an option: at this point the event has not been
        persisted, so discarding it loses the message outright rather than
        merely delaying it. Waiting is the honest response — it stops reading
        this one client's socket, TCP backpressure reaches their browser, and
        every other connection is unaffected because each has its own task.
        """
        if self.batch_size >= settings.MAX_PENDING_EVENTS:
            logger.warning(
                "Event buffer full, applying backpressure",
                pending=self.batch_size,
                limit=settings.MAX_PENDING_EVENTS,
            )
            try:
                async with asyncio.timeout(BACKPRESSURE_TIMEOUT_SECONDS):
                    while self.batch_size >= settings.MAX_PENDING_EVENTS:
                        await asyncio.sleep(0.01)
            except TimeoutError:
                # The batch loop is not draining. Refusing loudly beats queueing
                # into a process that is already failing.
                raise RuntimeError(
                    "Event buffer full and not draining; dropping inbound event"
                )

        self.batch[event.event_type].append(event)
        self.batch_size += 1

    async def _run_batch_loop(self):
        while True:
            start = asyncio.get_event_loop().time()

            # Wait for batch conditions
            while True:
                elapsed = asyncio.get_event_loop().time() - start

                # Exit if we have enough events OR time limit reached
                if self.batch_size >= settings.BATCH_SIZE:
                    break
                if elapsed >= (settings.BATCH_INTERVAL_MS / 1000.0):
                    break

                await asyncio.sleep(settings.BATCH_INTERVAL_MS / 1000.0)

            # Process batches
            if self.batch:
                # Take the batch away *before* awaiting, rather than clearing it
                # afterwards. The old code did `dispatch(deepcopy(batch))` and
                # then `batch.clear()`, so anything a client sent during the
                # dispatch — a Postgres round trip, easily longer than the 1ms
                # batch interval — was appended to the live dict and then wiped
                # without ever being dispatched. Messages were lost in ordinary
                # operation, invisibly, because they had already been persisted
                # and so reappeared on the next fetch.
                #
                # Swapping also makes the deepcopy unnecessary: nothing else
                # holds a reference to `pending` any more.
                pending = self.batch
                self.batch = defaultdict(list)
                self.batch_size = 0
                try:
                    await self.event_dispatcher.dispatch_events(pending)
                except Exception:
                    # This loop is the only thing draining the accumulator. If
                    # it dies the gateway silently stops delivering anything,
                    # so it must survive a bad batch.
                    logger.exception("Batch dispatch failed", events=len(pending))


event_queue = EventQueue()
