import asyncio
import time
from collections import defaultdict

import structlog
from libs.event.codec import EventCodec
from libs.event.event_pb2 import EventBatch as ProtobufEventBatch
from libs.event.schema import TargetType
from src.config import config
from src.grpc_connection_pool import GrpcConnectionPool
from src.grpc_endpoint_cache import GrpcEndpointCache
from src.redis_manager import RedisManager

logger = structlog.get_logger(__name__)

# The reclaim pass. Entries land in the group's pending list when a consumer reads
# them and never acknowledges: it died mid-batch, its shard moved and its worker
# was cancelled mid-batch, or a Redis error interrupted the batch before the ACK.
# Reads use ">", so nothing would ever look at them again.
RECLAIM_INTERVAL_SECONDS = 5
# Longer than a healthy batch can take, so an entry another consumer is still
# working on (a shard mid-handover) is not taken from it. A batch's slowest part
# is the gRPC send, bounded by GRPC_TIMEOUT.
RECLAIM_MIN_IDLE_MS = max(10_000, config.grpc_timeout * 3_000)
# Older than this is acknowledged without being delivered. Every event is a hint
# about state that is already committed, and clients resync on reconnect, so a
# late hint is worth less than none: a presence change a minute late puts a
# person back in a room they left. It also bounds the retries: an entry that
# keeps failing ages out after a handful of passes. See devnotes.md C4 and C5.
RECLAIM_MAX_AGE_MS = 60_000
RECLAIM_COUNT = 100
# Late is only harmless for some events. A message is deduplicated by id and
# sorted by time, and a notification or friend request makes the client refetch
# current state, so arriving late converges. Presence, edits and calls are
# deltas: a reclaimed "left" delivered after a newer "joined" takes someone out
# of a room they are in. Those are acknowledged undelivered, and the resync and
# roster reconcile that already exist repair what they would have said.
RECLAIM_DELIVERABLE = frozenset({"message", "notification", "friend_request"})
# How long stop() lets an in-flight batch finish before cancelling it. A batch is
# bounded by one gRPC timeout, so this is enough for every healthy one.
STOP_GRACE_SECONDS = config.grpc_timeout + 2
# Pages per pass, so one pass cannot monopolise the shard's worker
RECLAIM_MAX_PAGES = 10


def entry_event_type(data: dict) -> str:
    raw = data.get(b"event_type") or data.get("event_type") or b""
    return raw.decode() if isinstance(raw, bytes) else raw


def entry_age_ms(message_id: bytes | str, now_ms: int) -> int:
    """Age from a stream id, whose first half is the server's ms timestamp."""
    raw = message_id.decode() if isinstance(message_id, bytes) else message_id
    return now_ms - int(raw.split("-", 1)[0])


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
        # Reclaim straight away on start: a worker usually starts because its
        # shard just moved here, which is when stranded entries are likeliest.
        self._next_reclaim = 0.0

    def start(self):
        self.task = asyncio.create_task(self._read_and_process_stream())

    async def stop(self):
        """Let the current batch finish, then stop.

        It used to cancel straight away, which landed between a batch's send and
        its ACK often enough that every shard move stranded work: the next owner
        then reclaimed and sent it again, late and out of order. Now the loop
        sees `running` go false at its next iteration, and only a batch stuck
        past the grace period is cancelled.
        """
        self.running = False
        if not self.task or self.task.done():
            return
        try:
            await asyncio.wait_for(asyncio.shield(self.task), STOP_GRACE_SECONDS)
        except asyncio.TimeoutError:
            self.task.cancel()
        except Exception:
            # The loop handles its own errors; anything here is already logged
            pass

    async def _read_and_process_stream(self):
        while self.running:
            try:
                # In the same loop as reads, not a task of its own, so reclaimed
                # entries are delivered one batch at a time like everything else
                # on this shard.
                if time.monotonic() >= self._next_reclaim:
                    self._next_reclaim = time.monotonic() + RECLAIM_INTERVAL_SECONDS
                    await self._reclaim()

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

    async def _reclaim(self):
        """Deliver what another read stranded, or let it go if it is too old."""
        start_id: str | bytes = "0-0"
        for _ in range(RECLAIM_MAX_PAGES):
            start_id, claimed = await self.redis_manager.autoclaim(
                self.stream_name,
                self.consumer_group,
                self.consumer_id,
                RECLAIM_MIN_IDLE_MS,
                start_id,
                RECLAIM_COUNT,
            )
            if claimed:
                # Redis's clock, not ours: the id's timestamp was written by it
                now_ms = await self.redis_manager.server_time_ms()
                fresh = [
                    (message_id, data)
                    for message_id, data in claimed
                    if data
                    and entry_event_type(data) in RECLAIM_DELIVERABLE
                    and entry_age_ms(message_id, now_ms) <= RECLAIM_MAX_AGE_MS
                ]
                fresh_ids = {message_id for message_id, _ in fresh}
                stale = [mid for mid, _ in claimed if mid not in fresh_ids]
                if stale:
                    await self.redis_manager.batch_ack_messages(
                        self.stream_name, self.consumer_group, stale
                    )
                    logger.warning(
                        "Discarded stranded events too old or too order-sensitive to deliver late",
                        stream_name=self.stream_name,
                        events=len(stale),
                        max_age_ms=RECLAIM_MAX_AGE_MS,
                    )
                if fresh:
                    logger.warning(
                        "Reclaimed stranded events",
                        stream_name=self.stream_name,
                        events=len(fresh),
                    )
                    await self._process_batch([(self.stream_name.encode(), fresh)])
            if start_id in (b"0-0", "0-0"):
                return

    async def _process_batch(self, event_batch):
        """
        Process events from the Redis stream concurrently
        """

        gateway_batches = defaultdict(list)
        # Which routes led to each endpoint, so a dead one can be pruned from
        # exactly the places it was found
        routed_by: dict[str, tuple[set[str], set[str]]] = defaultdict(
            lambda: (set(), set())
        )
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
                    channels, users = routed_by[endpoint]
                    (users if event.target_type == TargetType.USER.value else channels).add(
                        event.target_id
                    )

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
                await self._prune_if_dead(endpoint, *routed_by[endpoint])

        await self.redis_manager.batch_ack_messages(
            stream_name_str,
            self.consumer_group,
            message_ids,
        )

    async def _prune_if_dead(
        self, endpoint: str, channel_ids: set[str], user_ids: set[str]
    ) -> None:
        """Take a crashed gateway out of the routes that led here.

        A gateway that exits cleanly removes its own routes as its sockets close.
        One that is SIGKILLed or OOM-killed removes nothing, and nothing else ever
        would: `channel:{id}:grpc_endpoints` has no expiry, so every later event
        for those channels was sent to an address that is not there, the first
        time at the cost of a full `GRPC_TIMEOUT` on this shard.

        Only on evidence of both: the delivery failed, and the gateway's heartbeat
        is gone. A live gateway that was merely slow keeps its routes. Best
        effort: a failure here leaves things as they were, never worse.
        """
        try:
            if await self.redis_manager.gateway_alive(endpoint):
                return
            await self.redis_manager.prune_endpoint(
                endpoint, sorted(channel_ids), sorted(user_ids)
            )
            logger.warning(
                "Pruned a dead gateway from its routes",
                endpoint=endpoint,
                channels=len(channel_ids),
                users=len(user_ids),
            )
        except Exception:
            logger.exception("Could not prune a dead gateway", endpoint=endpoint)

    async def _transmit_batch(self, endpoint: str, batch: ProtobufEventBatch):
        stub = await self.connection_pool.get_stub(endpoint)
        try:
            # Without a deadline a dead gateway blocks this worker's shard
            await stub.SendEvents(batch, timeout=config.grpc_timeout)
        except Exception as e:
            logger.error("Failed to send events to gRPC endpoint", error=e)
            raise e
