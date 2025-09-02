import asyncio
from collections import defaultdict
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from src.database import AsyncSessionLocal
from src.redis_manager import RedisManager

# from src.services.friend_request_event_dispatcher import FriendRequestEventDispatcher
from src.services.message_event_dispatcher import MessageEventDispatcher

from libs.event.schema import Event, EventType


class EventDispatcher:
    def __init__(self):
        self.redis_manager = RedisManager()
        self.session_factory = AsyncSessionLocal
        self.message_event_dispatcher = MessageEventDispatcher()
        # self.friend_request_event_dispatcher = FriendRequestEventDispatcher()

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
            await asyncio.gather(*persist_tasks)
            await session.commit()

        await self.redis_manager.batch_push_events_to_streams(batch)

    async def _persist_group(
        self, session: AsyncSession, event_type: str, events: List[Event]
    ):
        """
        Persist events of one type.
        You'd have type-specific handlers here.
        """
        if event_type == EventType.MESSAGE:
            # e.g. bulk insert messages
            await self.message_event_dispatcher.dispatch_event(session, events)
