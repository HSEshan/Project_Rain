import asyncio
import time
from typing import List

import structlog
from libs.rediskeys import RediKeys
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from src.config import config

logger = structlog.get_logger(__name__)


class LeaseManager:
    def __init__(self):
        self.redis: Redis | None = None
        self.num_streams = config.num_streams
        self.running = True
        self.suspect_consumers = {}

    async def connect(self, host: str, port: int, db: int):
        retries = 5
        for i in range(retries):
            try:
                self.redis = Redis(host=host, port=port, db=db)
                await self.redis.ping()
                logger.info("Connected to Redis")
                break
            except Exception as e:
                logger.error(f"Error connecting to Redis on attempt {i}: {e}")
                await asyncio.sleep(2)
        if not self.redis:
            raise Exception("Failed to connect to Redis")

    async def disconnect(self):
        await self.redis.aclose()

    async def ensure_consumer_groups(self):
        """
        Ensure that the consumer groups exist for the given streams.
        """
        for stream_id in range(self.num_streams):
            stream_name = RediKeys.stream_shard(stream_id)
            try:
                await self.redis.xgroup_create(
                    name=stream_name,
                    groupname="grpc_group",  # same group as consumers use
                    id="0",
                    mkstream=True,
                )
                logger.info(f"Created consumer group for {stream_name}")
            except ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise

    async def get_active_consumers(self) -> List[str]:
        consumers = await self.redis.smembers(RediKeys.event_consumers())
        active = []
        for cid in [cid.decode("utf-8") for cid in consumers]:
            ttl = await self.redis.ttl(RediKeys.heartbeat(cid))
            if ttl > 0:
                logger.debug(f"{cid} heartbeat TTL: {ttl}")
                active.append(cid)
                self.suspect_consumers.pop(cid, None)
            elif cid not in self.suspect_consumers:
                logger.warning(f"{cid} heartbeat expired, adding to suspect list")
                self.suspect_consumers[cid] = time.monotonic()

        for cid, timestamp in list(self.suspect_consumers.items()):
            if time.monotonic() - timestamp > 15:
                logger.warning(f"{cid} grace period expired, removing from redis")
                await self.redis.srem(RediKeys.event_consumers(), cid)
                self.suspect_consumers.pop(cid, None)

        logger.info(f"Active consumers: {active}")
        return active

    async def assign_leases(self):
        consumers = await self.get_active_consumers()
        if not consumers:
            logger.info("No active consumers")
            return

        leases_per_consumer = self.num_streams // len(consumers)
        remainder = self.num_streams % len(consumers)

        assignments = {}
        stream_id = 0

        for consumer in consumers:
            count = leases_per_consumer + (1 if remainder > 0 else 0)
            if remainder > 0:
                remainder -= 1

            for _ in range(count):
                stream_key = RediKeys.stream_shard(stream_id)
                assignments[stream_key] = consumer
                stream_id += 1

        await self.redis.hset(RediKeys.leases(), mapping=assignments)
        logger.info(f"Assigned leases to {len(consumers)} consumers")

    async def run(self):
        logger.info("Running...")
        await self.ensure_consumer_groups()
        next_lease = time.monotonic()
        while self.running:
            try:
                await self.assign_leases()
                # Avoid drift
                next_lease += 5
                sleep_duration = max(0, next_lease - time.monotonic())
                await asyncio.sleep(sleep_duration)
            except Exception as e:
                logger.error(f"Error: {e}")
                await asyncio.sleep(5)
