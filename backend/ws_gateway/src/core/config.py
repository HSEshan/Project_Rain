import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    DEFAULT_TTL_SECONDS: int

    NUM_SHARDS: int
    BATCH_SIZE: int
    BATCH_INTERVAL_MS: int

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str

    GRPC_HOST: str
    GRPC_PORT: int

    SECRET_KEY: str
    ALGORITHM: str

    @property
    def GRPC_ENDPOINT(self) -> str:
        """Address other instances reach *this* gateway on.

        It is written into `user:{id}:grpc_endpoint`, so it must resolve to this
        instance specifically. Compose runs a single gateway and `GRPC_HOST` is
        the service name, which happens to work. With replicas, every instance
        would advertise the same name and the consumer would fan events out to
        whichever container the DNS round-robin picked. Set `GRPC_HOST` per
        instance then — the pod hostname on Kubernetes, `os.uname().nodename`
        as a fallback.
        """
        return f"{self.GRPC_HOST}:{self.GRPC_PORT}"

    @property
    def ASYNC_DB_URL(self):
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env")


def get_settings() -> Settings:
    environment = os.getenv("ENVIRONMENT", "development")
    env_file = f"{environment}.env"
    return Settings(_env_file=env_file, _env_file_encoding="utf-8")


settings = get_settings()
