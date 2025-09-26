import asyncio
from collections import defaultdict
from copy import deepcopy
from typing import Dict, List

import structlog
from libs.event.schema import Event
from src.core.config import settings
from src.event.event_dispatcher import EventDispatcher

logger = structlog.get_logger()


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
                await self.event_dispatcher.dispatch_events(deepcopy(self.batch))
                self.batch.clear()
                self.batch_size = 0


event_queue = EventQueue()
