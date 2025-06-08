import os
from enum import Enum
from pathlib import Path

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
    SUPERUSER_EMAIL: str
    SUPERUSER_PASSWORD: str
    DOCS: bool

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def ASYNC_DB_URL(self):
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


def get_settings() -> SettingsFactory:
    environment = os.getenv("ENVIRONMENT", "development")
    env_file = f"{environment}.env"

    # Load .env if exists, but don’t fail if missing
    if Path(env_file).exists():
        env_file_to_load = env_file
    elif Path(".env").exists():
        env_file_to_load = ".env"
    else:
        env_file_to_load = None

    try:
        return SettingsFactory(_env_file=env_file_to_load, _env_file_encoding="utf-8")
    except Exception as e:
        print(f"Error loading settings: {e}")
        raise


settings: SettingsFactory = get_settings()
