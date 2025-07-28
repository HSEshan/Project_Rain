import hashlib
from collections import defaultdict

import structlog
from fastapi import WebSocket
from src.core.config import settings
from src.redis_manager import RedisManager

from libs.event.schema import Event

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

    async def add_client(self, client_id: str, websocket: WebSocket):
        """
        Add a client to the service.
        """
        await websocket.accept()
        self.clients[client_id] = websocket
        await self.redis_manager.set_user_instance(client_id, self.grpc_endpoint)
        channel_ids = await self.redis_manager.get_user_channel_ids(client_id)

        for channel_id in channel_ids:
            self.user_mapping.add_mapping(client_id, channel_id)
            await self.redis_manager.add_instance_to_channel(
                channel_id, self.grpc_endpoint
            )

        logger.info(f"Client {client_id} connected")

    async def remove_client(self, client_id: str):
        """
        Remove a client from the service.
        """
        del self.clients[client_id]
        self.user_mapping.remove_user_from_channels(client_id)
        await self.redis_manager.delete_user_instance(client_id)

    async def send_event(self, event: Event):
        """
        Send an event to a client.
        """
        if not event.receiver_id:
            logger.error(f"Event {event.event_id} has no receiver_id")
            return
        try:
            await self.clients[str(event.receiver_id)].send_json(
                event.model_dump(mode="json")
            )
            logger.info(f"Event {event.event_id} sent to {event.receiver_id}")
        except KeyError:
            logger.error(
                f"Client {event.receiver_id} not found. Current clients: {self.clients}"
            )

    async def handle_event(self, event: Event):
        """
        Push an event to the Redis stream.
        """
        shard_id = self.compute_shard_id(event.receiver_id)
        await self.redis_manager.push_event_to_stream(shard_id, event)
        logger.info(f"Event {event.event_id} pushed to Redis stream, shard: {shard_id}")

    def compute_shard_id(
        self, receiver_id: str, num_shards: int = settings.NUM_SHARDS
    ) -> str:
        """
        Compute the shard ID for a receiver ID.
        """
        hash_val = int(hashlib.sha256(str(receiver_id).encode()).hexdigest(), 16)
        return str(hash_val % num_shards)


websocket_manager = WebsocketManager()
