import os
from dataclasses import dataclass, fields


@dataclass
class Config:
    redis_host: str = os.getenv("REDIS_HOST")
    redis_port: int = int(os.getenv("REDIS_PORT"))
    redis_db: int = int(os.getenv("REDIS_DB"))
    num_streams: int = int(os.getenv("NUM_STREAMS"))

    def __post_init__(self):
        missing_vars = []
        for f in fields(self):
            value = getattr(self, f.name)
            if value is None:
                missing_vars.append(f.name.upper())
        if missing_vars:
            raise ValueError(f"Environment variables {missing_vars} are not set")


config = Config()
