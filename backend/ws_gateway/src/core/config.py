import os
import socket

from libs.event.shards import LEGACY_SHARD_COUNT_ENV, SHARD_COUNT_ENV
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    DEFAULT_TTL_SECONDS: int

    # Must equal rest_api's and the lease manager's, or events land on shards
    # nobody leases. Required here on purpose: the gateway is a publisher, and
    # its env files have always carried the line. `NUM_STREAMS` is the
    # deprecated spelling, still accepted (libs.event.shards).
    NUM_SHARDS: int = Field(
        validation_alias=AliasChoices(SHARD_COUNT_ENV, LEGACY_SHARD_COUNT_ENV),
    )

    BATCH_SIZE: int
    BATCH_INTERVAL_MS: int

    # Ceiling on events waiting to be persisted and published. Defaulted so an
    # env file written before this existed still boots. Reaching it means the
    # batch loop is not draining — almost always a slow or unreachable Postgres
    # — and producers wait rather than growing the process without limit.
    MAX_PENDING_EVENTS: int = 10_000

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str

    GRPC_HOST: str
    GRPC_PORT: int

    SECRET_KEY: str
    ALGORITHM: str

    # Address that routes to *this* instance specifically, overriding GRPC_HOST.
    #
    # This is the whole of the platform story, on purpose. The requirement is
    # not "support Kubernetes", it is "every instance must advertise an address
    # that reaches it and not a sibling", and that is one config value on every
    # platform. On Kubernetes it comes from the downward API and needs no
    # Kubernetes-aware code in this image:
    #
    #     env:
    #       - name: GRPC_ADVERTISE_HOST
    #         valueFrom:
    #           fieldRef:
    #             fieldPath: status.podIP
    #
    # A StatefulSet behind a headless Service can inject the stable pod FQDN the
    # same way; on plain VMs it is the LAN address. Leave it unset and the
    # single-replica behaviour is exactly what it was.
    GRPC_ADVERTISE_HOST: str = ""

    @property
    def GRPC_ENDPOINT(self) -> str:
        """Address other instances reach *this* gateway on.

        Written into `user:{id}:grpc_endpoint` and into each
        `channel:{id}:grpc_endpoints`, so it must resolve to this instance and
        not to a sibling. With `GRPC_HOST` set to the Compose service name and
        one replica running, it does. With replicas it would not: every instance
        advertises the same name, the name load-balances, and events land on a
        gateway that does not hold the socket and are dropped silently. Hence
        the override.

        Resolution order, most explicit first:

        1. `GRPC_ADVERTISE_HOST`, whatever the platform was told to inject.
        2. This container's own hostname, when it resolves to something that is
           not loopback. Under `docker compose --scale` each replica gets a
           distinct hostname that resolves on the compose network, so this is
           correct there too.
        3. `GRPC_HOST`, the historical single-replica default.

        Resolving the right address is necessary and **not** sufficient for
        running replicas. See devnotes.md Appendix A2 for the lifecycle work
        that still stands in the way: nothing deregisters a gateway on shutdown,
        and `channel:{id}:grpc_endpoints` has no expiry, so a crashed instance
        stays in it forever.
        """
        return f"{self._advertise_host()}:{self.GRPC_PORT}"

    def _advertise_host(self) -> str:
        if self.GRPC_ADVERTISE_HOST:
            return self.GRPC_ADVERTISE_HOST

        try:
            hostname = socket.gethostname()
            # Only useful if it actually resolves to a routable address. On a
            # misconfigured host it maps to 127.0.0.1, and advertising that
            # tells every other service to reach us at their own loopback.
            if hostname and not socket.gethostbyname(hostname).startswith("127."):
                return hostname
        except OSError:
            pass

        return self.GRPC_HOST

    @property
    def ASYNC_DB_URL(self):
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env")


def get_settings() -> Settings:
    environment = os.getenv("ENVIRONMENT", "development")
    env_file = f"{environment}.env"
    return Settings(_env_file=env_file, _env_file_encoding="utf-8")


settings = get_settings()
