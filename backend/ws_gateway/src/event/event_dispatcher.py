import asyncio
from collections import defaultdict
from typing import List

import structlog
from libs.event.schema import Event, EventType
from libs.logging import bind_event_context
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.config import AsyncSessionLocal
from src.database.models import *

# from src.services.friend_request_event_dispatcher import FriendRequestEventDispatcher
from src.message.dispatcher import MessageEventDispatcher
from src.redis.redis_manager import RedisManager
from src.websocket.manager import WebsocketManager

logger = structlog.get_logger()


class EventDispatcher:
    def __init__(self):
        self.redis_manager: RedisManager | None = None
        self.session_factory: AsyncSession = AsyncSessionLocal
        self.message_event_dispatcher = MessageEventDispatcher()
        self.websocket_manager: WebsocketManager | None = None
        # self.friend_request_event_dispatcher = FriendRequestEventDispatcher()

    def set_redis_manager(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager

    def set_websocket_manager(self, websocket_manager: WebsocketManager):
        self.websocket_manager = websocket_manager

    async def dispatch_events(self, batch: dict[str, list[Event]]):
        if not batch:
            return
        if not self.redis_manager:
            logger.error("Redis manager not set")
            return

        # Persist all events
        async with self.session_factory() as session:
            persist_tasks = [
                self._persist_group(session, event_type, group)
                for event_type, group in batch.items()
            ]
            success = await asyncio.gather(*persist_tasks, return_exceptions=True)
            for task in success:
                if isinstance(task, Exception):
                    logger.exception("One or more persist tasks failed")
                    logger.debug(f"Details: {task}")
                    await session.rollback()
                    return
            try:
                await session.commit()
                logger.debug("DB commit successful")
            except Exception:
                logger.exception("DB commit failed")
                await session.rollback()

        # Push events to Redis streams
        all_events: List[Event] = []
        for events in batch.values():
            all_events.extend(events)
        asyncio.create_task(self.redis_manager.batch_push_events_to_streams(all_events))

    async def _persist_group(
        self, session: AsyncSession, event_type: str, events: List[Event]
    ):
        """
        Persist events of one type.
        """
        try:
            if event_type == EventType.MESSAGE:
                await self.message_event_dispatcher.dispatch_events(session, events)
        except Exception:
            logger.exception("Persist group failed")
            return False
        return True

    @bind_event_context(event_arg_name="event")
    async def send_events_to_clients(self, events: List[Event]):

        # Group by user_id
        groups = defaultdict(list)  # user_id -> list[event_json]
        for event in events:
            user_ids = self.websocket_manager.user_mapping.get_channel_user_ids(
                event.receiver_id
            )
            if not user_ids:
                logger.debug(f"No user ids found for event: {event}")
                continue
            event_json = event.model_dump(mode="json")
            for user_id in user_ids:
                groups[user_id].append(event_json)

        tasks = []
        for user_id in groups:
            client_socket = self.websocket_manager.get_client_socket(user_id)
            for event_json in groups[user_id]:
                tasks.append(client_socket.send_json(event_json))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        success = sum(1 for result in results if result is None)

        logger.debug(f"Sends {success} / {len(groups)} successful")


event_dispatcher = EventDispatcher()
