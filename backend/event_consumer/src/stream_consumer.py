import asyncio
import time

import grpc
import structlog
from libs.event.codec import EventCodec
from libs.event.event_pb2 import Event as ProtobufEvent
from libs.logging import bind_event_context
from src.config import config
from src.grpc_connection_pool import GrpcConnectionPool
from src.grpc_endpoint_cache import GrpcEndpointCache
from src.redis_manager import RedisManager

logger = structlog.get_logger(__name__)


class RedisStreamConsumer:
    """
    Redis stream consumer service. It consumes events from Redis streams, identifies gRPC endpoints from Redis,
    and sends events to the gRPC endpoints.
    """

    def __init__(self, consumer_id: str):
        self.redis_manager: RedisManager | None = None
        self.consumer_id = consumer_id
        self.fetched_shards: list[str] = []
        self.consumer_group = "grpc_group"
        self.running = True
        self.connection_pool = GrpcConnectionPool(
            max_connections=config.max_grpc_connections,
        )
        self.shard_process_tasks: dict[str, asyncio.Task] = {}
        self.stream_semaphores: dict[str, asyncio.Semaphore] = {}
        self.grpc_endpoint_cache = GrpcEndpointCache()

    def set_redis_manager(self, redis_manager: RedisManager):
        self.redis_manager = redis_manager

    async def start(self):
        """Start the consumer and connection pool."""
        try:
            await self.connection_pool.start()
            await self.register()
            await self.grpc_endpoint_cache.set_redis_manager(self.redis_manager)
            await self.grpc_endpoint_cache.start()

        except Exception as e:
            logger.critical(
                f"Error starting consumer, consumer_id={self.consumer_id}",
                error=e,
            )
            raise

    async def stop(self):
        """Stop the consumer and cleanup connections."""
        self.running = False
        await self.connection_pool.stop()
        await self.grpc_endpoint_cache.stop()
        await self.unregister()
        logger.info(f"Consumer {self.consumer_id} stopped")

    async def register(self):
        await self.redis_manager.register_consumer(self.consumer_id)
        await self.redis_manager.send_heartbeat(self.consumer_id, ttl=15)
        logger.info(f"Consumer {self.consumer_id} registered")

    async def unregister(self):
        await self.redis_manager.unregister_consumer(self.consumer_id)
        logger.info(f"Consumer {self.consumer_id} unregistered")

    def create_stream_semaphore(self, stream_name: str):
        self.stream_semaphores[stream_name] = asyncio.Semaphore(
            config.grpc_max_concurrent_calls
        )

    async def heartbeat_loop(self):
        next_heartbeat = time.monotonic()
        while self.running:
            # Send heartbeat
            await self.redis_manager.send_heartbeat(self.consumer_id, ttl=15)
            # Avoid drift
            next_heartbeat += 5
            sleep_duration = max(0, next_heartbeat - time.monotonic())
            await asyncio.sleep(sleep_duration)

    async def consume_loop(self):
        while self.running:
            try:
                # Add timeout to prevent blocking indefinitely
                current_fetched_shards = await asyncio.wait_for(
                    self.redis_manager.fetch_leased_shards(self.consumer_id),
                    timeout=5.0,  # 5 second timeout
                )

                if current_fetched_shards != self.fetched_shards:
                    self.fetched_shards = current_fetched_shards
                    logger.info(f"Fetched shards updated: {self.fetched_shards}")

                # Launch concurrent tasks to read from each stream. Update on each lease call.
                for shard in self.fetched_shards:
                    if shard in self.shard_process_tasks:
                        continue
                    self.create_stream_semaphore(shard)
                    task = asyncio.create_task(self._read_and_process_stream(shard))
                    self.shard_process_tasks[shard] = task
                    logger.debug(f"Launched task for shard: {shard}")

                # Cleanup tasks that are not in the shards list
                for shard in list(self.shard_process_tasks.keys()):
                    if shard not in self.fetched_shards:
                        self.shard_process_tasks[shard].cancel()
                        del self.shard_process_tasks[shard]
                        logger.debug(f"Cancelled task for shard: {shard}")

                await asyncio.sleep(0.1)

            except asyncio.TimeoutError:
                logger.warning("Timeout fetching leased shards, retrying...")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in consume loop: {e}")
                await asyncio.sleep(1)

        logger.warning("Consume loop stopped")

    async def _read_and_process_stream(self, stream_name: str):
        while self.running:
            try:
                response = await self.redis_manager.read_stream(
                    self.consumer_id, stream_name, self.consumer_group
                )

                if response:
                    # Run in background
                    asyncio.create_task(self._process_events(response))
                else:
                    await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error reading from {stream_name}: {e}")
                await asyncio.sleep(1)

    async def _process_events(self, response):
        """
        Process events from the Redis stream concurrently with optimized task management.
        """
        for stream_name, events in response:
            stream_name_str = stream_name.decode("utf-8")
            semaphore = self.stream_semaphores[stream_name_str]

            # Pre-decode all messages to avoid repeated decoding
            decoded_events = []
            for message_id, message_data in events:
                decoded_data = {k.decode(): v.decode() for k, v in message_data.items()}
                decoded_events.append((message_id, decoded_data))

            # Process messages with controlled concurrency
            async def process_message_with_semaphore(message_id, event_data):
                async with semaphore:
                    return await self._process_single_message(
                        stream_name_str, message_id, event_data
                    )

            # Create tasks with proper semaphore control
            tasks = [
                process_message_with_semaphore(message_id, event_data)
                for message_id, event_data in decoded_events
            ]

            # Process all messages concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle results efficiently
            success_message_ids = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to process event: {result}")
                else:
                    success_message_ids.append(events[i][0])

            success_count = len(success_message_ids)
            total_count = len(events)

            if success_count > 0:
                logger.info(
                    f"Successfully processed {success_count} / {total_count} events from {stream_name_str}"
                )

                # Batch ACK successful messages
                await self.redis_manager.batch_ack_messages(
                    stream_name_str, self.consumer_group, success_message_ids
                )
            else:
                logger.warning(f"Failed to process all events from {stream_name_str}")

    @bind_event_context(event_arg_name="event_data")
    async def _process_single_message(
        self, stream_name: str, message_id: str, event_data: dict
    ):
        """Process a single message asynchronously with performance tracking."""
        try:
            # Start Redis lookup immediately
            grpc_endpoints_task = self.grpc_endpoint_cache.get_cached_endpoints(
                event_data["receiver_id"], event_data["event_type"]
            )

            # Create event while Redis lookup is happening
            event = EventCodec.to_grpc(event_data)

            # Wait for endpoints
            grpc_endpoints = await grpc_endpoints_task
            logger.debug(f"gRPC endpoints for event delivery: {grpc_endpoints}")
            if not grpc_endpoints:
                logger.warning(
                    f"No gRPC endpoints found for receiver: {event_data['receiver_id']}"
                )
                raise Exception(
                    f"No gRPC endpoints found for receiver: {event_data['receiver_id']}"
                )

            # Send to all endpoints concurrently
            send_tasks = []
            for grpc_endpoint in grpc_endpoints:
                task = self._send_to_grpc_endpoint(grpc_endpoint, event, message_id)
                send_tasks.append(task)

            # Wait for all sends to complete
            send_results = await asyncio.gather(*send_tasks, return_exceptions=True)

            # Check if at least one send succeeded
            successful_sends = sum(
                1 for result in send_results if not isinstance(result, Exception)
            )

            if successful_sends > 0:
                logger.debug(
                    f"ACK {message_id} from {stream_name} ({successful_sends}/{len(grpc_endpoints)} sends successful)"
                )
            else:
                logger.error(f"All gRPC sends failed for {message_id}")
                # Consider retry logic or dead letter queue

        except Exception as e:
            logger.error(f"Failed to process {message_id}: {e}")
            raise

    @bind_event_context(event_arg_name="event")
    async def _send_to_grpc_endpoint(
        self, grpc_endpoint: str, event: ProtobufEvent, message_id: str
    ):
        """Send event to a single gRPC endpoint with timeout and retry."""
        try:
            stub = await self.connection_pool.get_stub(grpc_endpoint)

            # Add timeout to prevent hanging
            await asyncio.wait_for(stub.SendEvent(event), timeout=config.grpc_timeout)
            logger.debug(f"Sent {event} to {grpc_endpoint}")
            return True

        except asyncio.TimeoutError:
            logger.error(f"Timeout sending to {grpc_endpoint} for message {message_id}")
            raise
        except grpc.RpcError as e:
            logger.error(f"gRPC error sending to {grpc_endpoint}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending to {grpc_endpoint}: {e}")
            raise
