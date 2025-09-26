import os
from dataclasses import dataclass, fields


@dataclass
class Config:
    redis_host: str = os.getenv("REDIS_HOST")
    redis_port: int = int(os.getenv("REDIS_PORT"))
    redis_db: int = int(os.getenv("REDIS_DB"))
    redis_xread_count: int = int(os.getenv("REDIS_XREAD_COUNT"))
    redis_xread_block: int = int(os.getenv("REDIS_XREAD_BLOCK"))
    consumer_group: str = os.getenv("CONSUMER_GROUP")
    heartbeat_ttl: int = int(os.getenv("HEARTBEAT_TTL"))
    grpc_timeout: int = int(os.getenv("GRPC_TIMEOUT"))
    max_grpc_connections: int = int(os.getenv("MAX_GRPC_CONNECTIONS"))
    log_level: str = os.getenv("LOG_LEVEL")
    log_format: str = os.getenv("LOG_FORMAT")

    def __post_init__(self):
        missing_vars = []
        for f in fields(self):
            value = getattr(self, f.name)
            if value is None:
                missing_vars.append(f.name.upper())
        if missing_vars:
            raise ValueError(f"Environment variables {missing_vars} are not set")


config = Config()
