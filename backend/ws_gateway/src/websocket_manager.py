from collections import defaultdict
from datetime import datetime, timezone

import structlog
from fastapi import WebSocket
from src.auth import CurrentUser
from src.redis_manager import RedisManager

logger = structlog.get_logger()


class UserMapping:
    """
    Mapping between user IDs and channel IDs.
    """

    def __init__(self):
        self.user_id_to_channel_ids: dict[str, set[str]] = defaultdict(set)
        self.channel_id_to_user_ids: dict[str, set[str]] = defaultdict(set)

    def add_mapping(self, user_id: str, channel_id: str):
        """
        Add a mapping between a user ID and a channel ID.
        """
        self.user_id_to_channel_ids[user_id].add(channel_id)
        self.channel_id_to_user_ids[channel_id].add(user_id)

    def get_user_channel_ids(self, user_id: str) -> list[str]:
        """
        Get the channel IDs for a user ID.
        """
        return self.user_id_to_channel_ids.get(user_id, [])

    def get_channel_user_ids(self, channel_id: str) -> list[str]:
        """
        Get the user IDs for a channel ID.
        """
        return self.channel_id_to_user_ids.get(channel_id, [])

    def remove_user_from_channels(self, user_id: str):
        """
        Remove a user from all channels. If a channel is empty, remove it.
        """
        channel_ids = self.user_id_to_channel_ids.pop(user_id)
        for channel_id in channel_ids:
            self.channel_id_to_user_ids[channel_id].remove(user_id)
            if not self.channel_id_to_user_ids[channel_id]:
                self.channel_id_to_user_ids.pop(channel_id)


class WebsocketManager:
    def __init__(self):
        self.clients: dict[str, WebSocket] = {}
        self.grpc_endpoint: str | None = None
        self.redis_manager: RedisManager | None = None
        self.user_mapping: UserMapping = UserMapping()

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
        self.clients[current_user.id] = websocket
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

        logger.info(f"Client {current_user.model_dump()} connected")
        logger.info(f"Client channel IDs: {channel_ids}")

    async def remove_client(self, client_id: str):
        """
        Remove a client from the service.
        """
        del self.clients[client_id]
        self.user_mapping.remove_user_from_channels(client_id)
        await self.redis_manager.delete_user_grpc_endpoint(client_id)

    def get_client_socket(self, client_id: str) -> WebSocket:
        """
        Get a client socket.
        """
        try:
            return self.clients[client_id]
        except KeyError:
            logger.error(f"Client {client_id} not found")
            logger.debug(f"Clients: {self.clients}")
            raise


websocket_manager = WebsocketManager()
