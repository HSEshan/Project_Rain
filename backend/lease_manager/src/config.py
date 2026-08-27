import os
from dataclasses import dataclass, fields

from libs.event.shards import resolve_shard_count


@dataclass
class Config:
    redis_host: str = os.getenv("REDIS_HOST")
    redis_port: int = int(os.getenv("REDIS_PORT"))
    redis_db: int = int(os.getenv("REDIS_DB"))
    # The lease manager is the only service that needs the count itself: it
    # creates the consumer groups and hands the shards out. `default=None`
    # keeps a missing value fatal, as it has always been, rather than letting
    # it lease a different number of shards than the publishers write to.
    # `NUM_SHARDS` is canonical, `NUM_STREAMS` still works (libs.event.shards).
    num_shards: int = resolve_shard_count(default=None).count

    def __post_init__(self):
        missing_vars = []
        for f in fields(self):
            value = getattr(self, f.name)
            if value is None:
                missing_vars.append(f.name.upper())
        if missing_vars:
            raise ValueError(f"Environment variables {missing_vars} are not set")


config = Config()
