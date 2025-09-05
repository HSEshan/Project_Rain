import asyncio
from collections import defaultdict
from typing import List

import structlog
from libs.event.schema import Event, EventType
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.config import AsyncSessionLocal

# from src.services.friend_request_event_dispatcher import FriendRequestEventDispatcher
from src.services.message_event_dispatcher import MessageEventDispatcher

logger = structlog.get_logger()


class EventDispatcher:
    def __init__(self):
        self.redis_manager = None
        self.session_factory = AsyncSessionLocal
        self.message_event_dispatcher = MessageEventDispatcher()
        # self.friend_request_event_dispatcher = FriendRequestEventDispatcher()

    def set_redis_manager(self, redis_manager):
        self.redis_manager = redis_manager

    async def dispatch_events(self, batch: dict[str, list[Event]]):
        if not batch:
            return

        # Group by event_type
        groups = defaultdict(list)
        for _, events in batch.items():
            for event in events:
                groups[event.event_type].append(event)

        async with self.session_factory() as session:
            persist_tasks = [
                self._persist_group(session, event_type, group)
                for event_type, group in groups.items()
            ]
            success = await asyncio.gather(*persist_tasks, return_exceptions=True)
            for task in success:
                if isinstance(task, Exception):
                    logger.exception("Persist tasks failed")
                    logger.debug(f"Details: {task}")
                    await session.rollback()
                    return
            try:
                await session.commit()
                logger.debug("DB commit successful")
            except Exception:
                logger.exception("DB commit failed")
                await session.rollback()

        try:
            await self.redis_manager.batch_push_events_to_streams(batch)
            logger.debug("Redis batch push successful")
        except Exception:
            logger.exception("Redis batch push failed")

    async def _persist_group(
        self, session: AsyncSession, event_type: str, events: List[Event]
    ):
        """
        Persist events of one type.
        """
        if event_type == EventType.MESSAGE:
            logger.debug(f"Persisting message events: {events}")
            await self.message_event_dispatcher.dispatch_events(session, events)
