import asyncio
from collections import OrderedDict

import grpc
import structlog
from libs.event import event_pb2_grpc

logger = structlog.get_logger(__name__)


class GrpcConnectionPool:
    """
    Simple LRU-based gRPC connection pool optimized for real-time messaging.
    No background cleanup tasks - connections are evicted only when pool is full.
    """

    def __init__(self, max_connections: int):
        self._channels = OrderedDict()  # LRU cache: oldest first
        self._max_connections = max_connections
        self._lock = asyncio.Lock()

    async def start(self):
        """No-op for compatibility - no background tasks needed."""
        logger.info(
            f"gRPC connection pool started with max {self._max_connections} connections"
        )

    async def stop(self):
        """Close all connections."""
        async with self._lock:
            for endpoint, channel in self._channels.items():
                try:
                    await channel.close()
                except Exception as e:
                    logger.warning(f"Error closing channel for {endpoint}: {e}")
            self._channels.clear()
            logger.info("gRPC connection pool stopped")

    async def get_stub(self, endpoint: str):
        """
        Get or create a gRPC stub for the endpoint.
        Uses simple LRU eviction when pool is full.
        """
        async with self._lock:
            # Check if channel exists
            if endpoint in self._channels:
                # Move to end (most recently used)
                self._channels.move_to_end(endpoint)
                return event_pb2_grpc.EventServiceStub(self._channels[endpoint])

            # Evict oldest connection if pool is full
            if len(self._channels) >= self._max_connections:
                oldest_endpoint, oldest_channel = self._channels.popitem(last=False)
                try:
                    await oldest_channel.close()
                    logger.debug(f"Evicted connection to {oldest_endpoint}")
                except Exception as e:
                    logger.warning(
                        f"Error closing evicted channel {oldest_endpoint}: {e}"
                    )

            # Create new channel with optimized settings for real-time messaging
            channel = grpc.aio.insecure_channel(
                endpoint,
                options=[
                    # Keep connections alive for real-time messaging
                    ("grpc.keepalive_time_ms", 30000),  # 30 seconds
                    ("grpc.keepalive_timeout_ms", 5000),  # 5 seconds
                    ("grpc.keepalive_permit_without_calls", True),
                    # HTTP/2 settings for better performance
                    ("grpc.http2.max_pings_without_data", 0),
                    ("grpc.http2.min_time_between_pings_ms", 10000),
                    (
                        "grpc.http2.min_ping_interval_without_data_ms",
                        300000,
                    ),  # 5 minutes
                    # Connection settings
                    ("grpc.max_receive_message_length", 4 * 1024 * 1024),  # 4MB
                    ("grpc.max_send_message_length", 4 * 1024 * 1024),  # 4MB
                ],
            )

            # Add to end (most recently used)
            self._channels[endpoint] = channel
            logger.debug(f"Created new connection to {endpoint}")
            return event_pb2_grpc.EventServiceStub(channel)

    async def close_connection(self, endpoint: str):
        """Manually close a specific connection (useful for testing/debugging)."""
        async with self._lock:
            if endpoint in self._channels:
                try:
                    await self._channels[endpoint].close()
                    del self._channels[endpoint]
                    logger.info(f"Manually closed connection to {endpoint}")
                except Exception as e:
                    logger.warning(f"Error closing connection to {endpoint}: {e}")

    def is_connected(self, endpoint: str) -> bool:
        """Check if a connection exists for the endpoint."""
        return endpoint in self._channels
