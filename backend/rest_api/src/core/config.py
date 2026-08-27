import logging
import os
from enum import Enum
from pathlib import Path

from libs.event.shards import (
    DEFAULT_NUM_SHARDS,
    LEGACY_SHARD_COUNT_ENV,
    SHARD_COUNT_ENV,
)
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ENVIRONMENT(Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class SettingsFactory(BaseSettings):

    ENVIRONMENT: ENVIRONMENT
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    SECRET_KEY: str
    ALGORITHM: str
    BCRYPT_ROUNDS: int
    SUPERUSER_EMAIL: str
    SUPERUSER_PASSWORD: str
    DOCS: bool

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Realtime publishing. This must equal the gateway's and the lease
    # manager's, or events land on shards nobody leases and are discarded in
    # silence. `NUM_STREAMS` is the deprecated spelling, still accepted so an
    # env file written before the rename keeps working (libs.event.shards).
    #
    # The default is the sharp edge: an env file that omits the line entirely
    # gets 16 while the rest of the deployment runs 2, and nothing looks wrong.
    # It stays because making it required turns a missing line into a
    # crash-loop on deploy. `register_shard_count` catches the disagreement at
    # startup instead, and `check_config.py` catches it before the deploy.
    NUM_SHARDS: int = Field(
        default=DEFAULT_NUM_SHARDS,
        validation_alias=AliasChoices(SHARD_COUNT_ENV, LEGACY_SHARD_COUNT_ENV),
    )

    # Demo account. Off by default so a fresh or private deployment does not
    # silently expose a tokenless login route; the seeder only runs when this
    # is on. See src/demo/.
    DEMO_ENABLED: bool = False

    # Voice (LiveKit SFU). The key/secret pair must match the one the livekit
    # container is started with — rest_api mints the join tokens. Defaulted so
    # that an env file written before voice existed still boots; the voice
    # endpoints return 503 while the secret is empty rather than minting
    # tokens nothing will accept.
    LIVEKIT_API_KEY: str = "devkey"
    LIVEKIT_API_SECRET: str = ""
    # Path the browser reaches LiveKit on, same origin as the app (Caddy
    # proxies it). Not a full URL: rest_api does not know the public host.
    LIVEKIT_PUBLIC_PATH: str = "/livekit"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def ASYNC_DB_URL(self):
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


def get_settings() -> SettingsFactory:
    logger = logging.getLogger(__name__)
    if not os.getenv("ENVIRONMENT"):
        logger.info("ENVIRONMENT is not set, defaulting to development")
        os.environ["ENVIRONMENT"] = "development"
    env_file = f"{os.environ["ENVIRONMENT"]}.env"

    # Load .env if exists, but don’t fail if missing
    if Path(env_file).exists():
        env_file_to_load = env_file
        logger.info(f"Loading {env_file}")
    elif Path(".env").exists():
        env_file_to_load = ".env"
        logger.info("Loading .env")
    else:
        env_file_to_load = None
        logger.info(f"No env file loaded")

    try:
        return SettingsFactory(_env_file=env_file_to_load, _env_file_encoding="utf-8")
    except Exception as e:
        logger.info(f"Error loading settings: {e}")
        raise


settings: SettingsFactory = get_settings()
