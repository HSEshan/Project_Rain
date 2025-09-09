from datetime import datetime, timezone

import structlog
from fastapi import WebSocket
from src.auth.models import CurrentUser
from src.redis.redis_manager import RedisManager
from src.websocket.mapping import UserMapping

logger = structlog.get_logger()


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
        logger.info(f"Client {client_id} disconnected")

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
