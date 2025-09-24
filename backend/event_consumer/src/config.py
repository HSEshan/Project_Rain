import os
from dataclasses import dataclass, fields


@dataclass
class Config:
    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_xread_count: int = int(os.getenv("REDIS_XREAD_COUNT", "100"))
    redis_xread_block: int = int(os.getenv("REDIS_XREAD_BLOCK", "25"))
    consumer_group: str = os.getenv("CONSUMER_GROUP", "grpc_group")
    heartbeat_ttl: int = int(os.getenv("HEARTBEAT_TTL", "15"))
    grpc_timeout: int = int(os.getenv("GRPC_TIMEOUT", "5"))
    max_grpc_connections: int = int(os.getenv("MAX_GRPC_CONNECTIONS", "100"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = os.getenv("LOG_FORMAT", "json")

    def __post_init__(self):
        missing_vars = []
        for f in fields(self):
            value = getattr(self, f.name)
            if value is None:
                missing_vars.append(f.name.upper())
        if missing_vars:
            raise ValueError(f"Environment variables {missing_vars} are not set")


config = Config()
