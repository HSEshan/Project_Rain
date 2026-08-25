import asyncio
from collections import defaultdict

import structlog
from libs.event.codec import EventCodec
from libs.event.event_pb2 import EventBatch as ProtobufEventBatch
from src.config import config
from src.grpc_connection_pool import GrpcConnectionPool
from src.grpc_endpoint_cache import GrpcEndpointCache
from src.redis_manager import RedisManager

logger = structlog.get_logger(__name__)


class StreamWorker:
    def __init__(
        self,
        stream_name,
        consumer_id: str,
        connection_pool: GrpcConnectionPool,
        grpc_endpoint_cache: GrpcEndpointCache,
        redis_manager: RedisManager,
    ):
        self.redis_manager = redis_manager
        self.consumer_id = consumer_id
        self.consumer_group = "grpc_group"
        self.stream_name = stream_name
        self.running = True
        self.connection_pool = connection_pool
        self.grpc_endpoint_cache = grpc_endpoint_cache
        self.event_loop = asyncio.get_running_loop()
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self._read_and_process_stream())

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()

    async def _read_and_process_stream(self):
        while self.running:
            try:
                event_batch = await self.redis_manager.read_stream(
                    self.consumer_id, self.stream_name, self.consumer_group
                )

                if event_batch:
                    # Awaited, not detached. As a background task its exceptions
                    # went nowhere, and two batches from the same shard could be
                    # in flight at once — which quietly undid the ordering the
                    # whole sharding scheme exists to provide. One batch at a
                    # time per shard is the guarantee; shards run concurrently.
                    await self._process_batch(event_batch)
                else:
                    await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(
                    "Error reading from stream", stream_name=self.stream_name, error=e
                )
                await asyncio.sleep(1)

    async def _process_batch(self, event_batch):
        """
        Process events from the Redis stream concurrently
        """

        gateway_batches = defaultdict(list)
        stream_name_str = event_batch[0][0].decode("utf-8")
        message_ids = []
        for _, messages in event_batch:

            for message_id, message_data in messages:
                message_ids.append(message_id)
                decoded_data = {k.decode(): v.decode() for k, v in message_data.items()}
                event = EventCodec.to_grpc(decoded_data)
                endpoints = await self.grpc_endpoint_cache.get_cached_endpoints(
                    event.target_id, event.target_type
                )
                if not endpoints:
                    logger.warning(
                        "No gRPC endpoints found for target",
                        target_type=event.target_type,
                        target_id=event.target_id,
                    )
                    continue
                for endpoint in endpoints:
                    gateway_batches[endpoint].append(event)

        endpoints = list(gateway_batches)
        results = await asyncio.gather(
            *(
                self._transmit_batch(endpoint, ProtobufEventBatch(events=events))
                for endpoint, events in gateway_batches.items()
            ),
            return_exceptions=True,
        )

        # One unreachable gateway must not cost the whole batch.
        #
        # This used to re-raise the first exception, before the ACK, from inside
        # a detached task whose exception nobody observed. The effect was that a
        # single dead endpoint discarded every entry in the batch — including
        # the ones already delivered to other gateways — and because reads use
        # ">" and nothing runs XAUTOCLAIM, those entries sat in the pending list
        # forever. Not retried: lost.
        #
        # So: acknowledge what was handled, and drop the failing endpoint from
        # the cache so the next lookup re-resolves it from Redis instead of
        # serving a dead address for the rest of the TTL. Events already handed
        # to a failing endpoint are lost until there is a reclaim loop; that is
        # a bounded, logged loss rather than an unbounded silent one.
        for endpoint, result in zip(endpoints, results):
            if isinstance(result, Exception):
                logger.error(
                    "Delivery to gateway failed, dropping it from the cache",
                    endpoint=endpoint,
                    events=len(gateway_batches[endpoint]),
                    error=str(result),
                )
                self.grpc_endpoint_cache.forget_endpoint(endpoint)

        await self.redis_manager.batch_ack_messages(
            stream_name_str,
            self.consumer_group,
            message_ids,
        )

    async def _transmit_batch(self, endpoint: str, batch: ProtobufEventBatch):
        stub = await self.connection_pool.get_stub(endpoint)
        try:
            # Without a deadline a dead gateway blocks this worker's shard
            await stub.SendEvents(batch, timeout=config.grpc_timeout)
        except Exception as e:
            logger.error("Failed to send events to gRPC endpoint", error=e)
            raise e
