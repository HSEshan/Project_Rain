import os
from dataclasses import dataclass


@dataclass
class Config:
    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    consumer_group: str = os.getenv("CONSUMER_GROUP", "grpc_group")
    heartbeat_ttl: int = int(os.getenv("HEARTBEAT_TTL", "15"))
    grpc_timeout: int = int(os.getenv("GRPC_TIMEOUT", "5"))
    max_grpc_connections: int = int(os.getenv("MAX_GRPC_CONNECTIONS", "1000"))
    grpc_max_concurrent_calls: int = int(os.getenv("GRPC_MAX_CONCURRENT_CALLS", "200"))


config = Config()
