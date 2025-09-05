import asyncio
import hashlib
from time import time
from typing import Dict, List

import structlog
from libs.event.schema import Event
from libs.logging import bind_event_context
from src.core.config import settings
from src.redis_manager import RedisManager
from src.services.event_dispatcher import EventDispatcher
from src.websocket_manager import WebsocketManager

logger = structlog.get_logger()

BATCH_SIZE = 100
BATCH_INTERVAL_MS = 0.1


class EventProcessor:
    def __init__(self):
        self.websocket_manager: WebsocketManager | None = None
        self.redis_manager: RedisManager | None = None
        self.event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._batch_task: asyncio.Task | None = None
        self.event_dispatcher = EventDispatcher()
        self.event_send_log = [0, time()]

    def set_websocket_manager(self, websocket_manager: WebsocketManager):
        self.websocket_manager = websocket_manager

    def set_redis_manager(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager
        self.event_dispatcher.set_redis_manager(redis_manager)

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
        logger.debug(f"Enqueuing event: {event}")
        await self.event_queue.put(event)

    async def _run_batch_loop(self):
        while True:
            batch: Dict[str, List[Event]] = {}
            start = asyncio.get_event_loop().time()

            while len(batch) < BATCH_SIZE:
                timeout = BATCH_INTERVAL_MS / 1000.0
                elapsed = asyncio.get_event_loop().time() - start
                remaining = max(0, timeout - elapsed)

                try:
                    event = await asyncio.wait_for(
                        self.event_queue.get(), timeout=remaining
                    )
                    shard_id = self._compute_shard_id(event.event_id)
                    batch.setdefault(shard_id, []).append(event)
                except asyncio.TimeoutError:
                    break

            if batch:
                await self.event_dispatcher.dispatch_events(batch)

    @bind_event_context(event_arg_name="event")
    async def send_event_to_clients(self, event: Event):

        receiver_ids = self.websocket_manager.user_mapping.get_channel_user_ids(
            event.receiver_id
        )

        if not receiver_ids:
            logger.debug(f"No receiver ids found for event: {event}")
            logger.debug(f"Mapping: {self.websocket_manager.user_mapping}")
            return

        event_json = event.model_dump(mode="json")

        tasks = []
        for receiver_id in receiver_ids:
            client_socket = self.websocket_manager.get_client_socket(receiver_id)
            tasks.append(client_socket.send_json(event_json))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        success = sum(1 for result in results if result is None)

        logger.debug(f"Sends {success} / {len(receiver_ids)} successful")

    def _compute_shard_id(
        self, receiver_id: str, num_shards: int = settings.NUM_SHARDS
    ) -> str:
        hash_val = int(hashlib.sha256(str(receiver_id).encode()).hexdigest(), 16)
        return str(hash_val % num_shards)


event_processor = EventProcessor()
