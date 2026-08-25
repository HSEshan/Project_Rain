import asyncio
from collections import defaultdict
from typing import List

import structlog
from libs.event.schema import CHANNELS_CHANGED_FLAG, Event, EventType, TargetType
from libs.logging import bind_event_context
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.config import AsyncSessionLocal
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
            results = await asyncio.gather(*persist_tasks, return_exceptions=True)
            failures = [r for r in results if isinstance(r, Exception)]
            if failures:
                logger.error(
                    "Persist failed, not publishing this batch",
                    failed_groups=len(failures),
                    error=str(failures[0]),
                )
                await session.rollback()
                return
            try:
                await session.commit()
                logger.debug("DB commit successful")
            except Exception:
                logger.exception("DB commit failed, not publishing this batch")
                await session.rollback()
                # Returning here is the point. Without it the code fell through
                # and published anyway, so a message that had just been rolled
                # back was delivered live and then vanished on the next fetch —
                # announcing something that never happened.
                return

        # Push events to Redis streams.
        #
        # Awaited, not fired off with create_task. As a detached task its
        # exceptions went to an unobserved future and were swallowed, so a Redis
        # outage silently dropped every event with nothing in the logs. Awaiting
        # also makes the stall real: if Redis is slow the batch loop slows down
        # with it, which is what backpressure is supposed to look like.
        all_events: List[Event] = []
        for events in batch.values():
            all_events.extend(events)
        try:
            await self.redis_manager.batch_push_events_to_streams(all_events)
        except Exception:
            # The messages are already committed, so this costs live delivery
            # only: clients pick them up on their next fetch or on reconnect.
            logger.exception("Failed to publish batch to Redis", events=len(all_events))

    async def _persist_group(
        self, session: AsyncSession, event_type: str, events: List[Event]
    ):
        """Persist events of one type.

        Deliberately lets exceptions propagate. It used to catch them and return
        `False`, while the caller tested `isinstance(result, Exception)` — which
        a `False` never satisfies, so the rollback path was unreachable and a
        failed insert was followed by a commit and a publish.
        """
        if event_type == EventType.MESSAGE:
            await self.message_event_dispatcher.dispatch_events(session, events)

    @bind_event_context(event_arg_name="event")
    async def send_events_to_clients(self, events: List[Event]):

        # Group by user_id
        groups = defaultdict(list)  # user_id -> list[event_json]
        for event in events:
            user_ids = self._resolve_recipients(event)
            if not user_ids:
                logger.debug(f"No user ids found for event: {event}")
                continue
            event_json = event.model_dump(mode="json")
            for user_id in user_ids:
                groups[user_id].append(event_json)

        await self._apply_side_effects(events)

        tasks = []
        for user_id in groups:
            # The consumer fans out per gateway, but a user may have
            # disconnected in the meantime — skip them, do not fail the batch
            client_sockets = self.websocket_manager.get_client_sockets(user_id)
            if not client_sockets:
                logger.debug(f"Client {user_id} is not on this instance, skipping")
                continue
            for event_json in groups[user_id]:
                # One user can hold several sockets (multiple tabs); each gets
                # its own copy
                for client_socket in client_sockets:
                    tasks.append(client_socket.send_json(event_json))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            logger.warning(f"{len(failures)} / {len(tasks)} sends failed")
        logger.debug(f"Sends {len(tasks) - len(failures)} / {len(tasks)} successful")

    def _resolve_recipients(self, event: Event) -> List[str]:
        """User-addressed events name their recipient directly; channel-addressed
        ones fan out to whichever members of that channel are on this gateway.

        Reads `target_type` off the event rather than inferring it from the
        event type. An event that predates the field still arrives with it set,
        because `Event` fills it in from `receiver_id` on construction.
        """
        if event.target_type is TargetType.USER:
            return [event.user_id]
        return list(
            self.websocket_manager.user_mapping.get_channel_user_ids(event.channel_id)
        )

    async def _apply_side_effects(self, events: List[Event]):
        """Some events change what this gateway needs to know before it can
        deliver the next message — a user who just joined a channel is not in
        this instance's mapping yet."""
        changed_user_ids = {
            event.target_id
            for event in events
            if (event.metadata or {}).get(CHANNELS_CHANGED_FLAG)
        }
        for user_id in changed_user_ids:
            await self.websocket_manager.refresh_user_channels(user_id)


event_dispatcher = EventDispatcher()
