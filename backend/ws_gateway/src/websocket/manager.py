import asyncio
from datetime import datetime, timezone

import structlog
from fastapi import WebSocket
from src.auth.models import CurrentUser
from src.redis.redis_manager import RedisManager
from src.websocket.mapping import UserMapping

logger = structlog.get_logger()


class WebsocketManager:
    """Sockets held by this gateway instance.

    A user may hold several at once — a second browser tab, or the overlap
    while a reconnect replaces a dying socket. Every one of them gets the
    user's events, and the user's routing (`user:{id}:grpc_endpoint`, the
    channel endpoint sets) is only torn down when the last one goes away.
    """

    def __init__(self):
        self.clients: dict[str, set[WebSocket]] = {}
        # One lock per user, held across every routing change for that user.
        # Connect, disconnect and refresh each walk the user's channels with an
        # await per Redis call, and a reload is exactly a disconnect and a
        # connect at the same moment: interleaved, the teardown removed routes
        # the new socket had just added and then deleted its user endpoint,
        # leaving a connected client that silently received nothing. Never
        # evicted: an entry is one small object per user who ever connected,
        # and evicting one while a coroutine waits on it would hand the next
        # caller a second, unrelated lock.
        self._locks: dict[str, asyncio.Lock] = {}
        self.grpc_endpoint: str | None = None
        self.redis_manager: RedisManager | None = None
        self.user_mapping: UserMapping = UserMapping()

    def _lock(self, user_id: str) -> asyncio.Lock:
        return self._locks.setdefault(user_id, asyncio.Lock())

    def set_grpc_endpoint(self, grpc_endpoint: str):
        """
        Set the gRPC endpoint for the service.
        """
        self.grpc_endpoint = grpc_endpoint
        logger.info(f"gRPC endpoint set to {grpc_endpoint}")

    def set_redis_manager(self, redis_manager: RedisManager):
        """
        Set the Redis manager for the service.
        """
        self.redis_manager = redis_manager
        logger.info("Redis manager set")

    async def add_client(self, current_user: CurrentUser, websocket: WebSocket):
        """
        Add a client to the service - set the user's gRPC endpoint, then add this endpoint to the user's channels
        """
        await websocket.accept()

        async with self._lock(current_user.id):
            await self._register(current_user, websocket)

    async def _register(self, current_user: CurrentUser, websocket: WebSocket):
        sockets = self.clients.setdefault(current_user.id, set())
        sockets.add(websocket)

        expiration = datetime.fromtimestamp(current_user.exp, tz=timezone.utc)
        ttl_seconds = int((expiration - datetime.now(timezone.utc)).total_seconds())
        await self.redis_manager.set_user_grpc_endpoint(
            current_user.id, self.grpc_endpoint, ttl_seconds
        )

        channel_ids = await self.redis_manager.get_user_channel_ids(current_user.id)

        for channel_id in channel_ids:
            self.user_mapping.add_mapping(current_user.id, channel_id)
            await self.redis_manager.add_grpc_endpoint_to_channel(
                channel_id, self.grpc_endpoint
            )

        logger.info(
            f"Client {current_user.model_dump()} connected", sockets=len(sockets)
        )
        logger.info(f"Client channel IDs: {channel_ids}")

    async def refresh_user_channels(self, user_id: str):
        """
        Re-read a connected user's channel membership.

        REST mutations (guild invite accepted, channel created) change
        membership behind this gateway's back. The cached set is dropped so the
        next read hits Postgres, and any new channel is registered against this
        instance's gRPC endpoint — otherwise the user would receive nothing from
        that channel until they reconnect.
        """
        async with self._lock(user_id):
            await self._refresh(user_id)

    async def _refresh(self, user_id: str):
        if user_id not in self.clients:
            return

        await self.redis_manager.delete_user_channels(user_id)
        channel_ids = await self.redis_manager.get_user_channel_ids(user_id)
        known_channel_ids = set(self.user_mapping.get_user_channel_ids(user_id))

        for channel_id in channel_ids:
            if channel_id in known_channel_ids:
                continue
            self.user_mapping.add_mapping(user_id, channel_id)
            await self.redis_manager.add_grpc_endpoint_to_channel(
                channel_id, self.grpc_endpoint
            )

        removed_channel_ids = known_channel_ids - set(channel_ids)
        for channel_id in removed_channel_ids:
            if self.user_mapping.remove_mapping(user_id, channel_id):
                await self.redis_manager.remove_grpc_endpoint_from_channel(
                    channel_id, self.grpc_endpoint
                )

        logger.info(f"Refreshed channels for {user_id}: {channel_ids}")

    async def remove_client(self, client_id: str, websocket: WebSocket | None = None):
        """
        Remove one of a client's sockets.

        `websocket` identifies which socket is going away. Only the last one
        tears down the user's routing — otherwise closing one tab would unroute
        the tab that is still open.
        """
        async with self._lock(client_id):
            await self._unregister(client_id, websocket)

    async def _unregister(self, client_id: str, websocket: WebSocket | None):
        sockets = self.clients.get(client_id)
        if not sockets:
            return

        if websocket is not None:
            sockets.discard(websocket)
        else:
            # No socket named: the caller is dropping the client entirely
            sockets.clear()

        if sockets:
            logger.info(
                f"Socket closed for {client_id}, {len(sockets)} still connected"
            )
            return

        del self.clients[client_id]
        empty_channel_ids = self.user_mapping.remove_user_from_channels(client_id)
        for channel_id in empty_channel_ids:
            await self.redis_manager.remove_grpc_endpoint_from_channel(
                channel_id, self.grpc_endpoint
            )
        await self.redis_manager.delete_user_grpc_endpoint(client_id)
        logger.info(f"Client {client_id} disconnected")

    def get_client_sockets(self, client_id: str) -> list[WebSocket]:
        """
        Every socket this client holds on this instance; empty if none.
        """
        return list(self.clients.get(client_id, ()))


websocket_manager = WebsocketManager()
