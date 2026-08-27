"""The shard count: one number, several services, two env var names of history.

Every event is written onto `stream_shard:{hash(target) % N}`. `N` therefore has
to be the same number everywhere it is used, or a producer writes onto a shard
that nobody leases and the event is discarded in silence. Historically it was
spelled `NUM_SHARDS` by the producers (rest_api, ws_gateway) and `NUM_STREAMS`
by lease_manager, which is two names for one value and exactly the shape of
configuration that drifts.

`NUM_SHARDS` is now the canonical name and `NUM_STREAMS` is a deprecated alias
that is still accepted, so an env file written before this change keeps working.
Renaming an env var outright would be a flag day (every file on the box has to
change at the same moment as the images) and there is no CI/CD to coordinate
one; this is the same expand-and-contract shape the event addressing migration
used. The alias goes away in a later release, once no deployed env file uses it.

Note that `event_consumer` is **not** part of the invariant: it discovers its
shards from the leases hash, so it never needs the count. Its env files carry a
`NUM_STREAMS` line that nothing reads.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Mapping, NamedTuple

import structlog

if TYPE_CHECKING:  # keep this module importable without redis installed
    from redis.asyncio import Redis

logger = structlog.get_logger()

DEFAULT_NUM_SHARDS = 16

SHARD_COUNT_ENV = "NUM_SHARDS"
LEGACY_SHARD_COUNT_ENV = "NUM_STREAMS"
# Order is priority: the canonical name wins when both are set.
SHARD_COUNT_ENV_NAMES = (SHARD_COUNT_ENV, LEGACY_SHARD_COUNT_ENV)

# Hash of service name -> the shard count that service booted with. Diagnostic
# only; nothing routes off it.
SHARD_COUNT_KEY = "config:shard_count"
SHARD_COUNT_TTL_SECONDS = 24 * 60 * 60


class ShardCount(NamedTuple):
    count: int
    source: str
    """Env var the value came from, or "default"."""


def resolve_shard_count(
    env: Mapping[str, str] | None = None,
    default: int | None = DEFAULT_NUM_SHARDS,
) -> ShardCount:
    """Read the shard count from the environment, canonical name first.

    Pass `default=None` for a service that must not start without one.
    Services whose settings are pydantic models express the same preference
    with `AliasChoices(SHARD_COUNT_ENV, LEGACY_SHARD_COUNT_ENV)`, so that
    pydantic still reads its own dotenv file rather than only `os.environ`.
    """
    env = os.environ if env is None else env

    for name in SHARD_COUNT_ENV_NAMES:
        raw = env.get(name)
        if raw is None or not str(raw).strip():
            continue
        try:
            count = int(str(raw).strip())
        except ValueError as e:
            raise ValueError(f"{name} is not an integer: {raw!r}") from e
        if count < 1:
            raise ValueError(f"{name} must be at least 1, got {count}")
        if name == LEGACY_SHARD_COUNT_ENV:
            logger.warning(
                "Shard count read from a deprecated env var; rename it",
                deprecated=LEGACY_SHARD_COUNT_ENV,
                use=SHARD_COUNT_ENV,
                num_shards=count,
            )
        return ShardCount(count, name)

    if default is None:
        raise ValueError(
            f"Neither {SHARD_COUNT_ENV} nor {LEGACY_SHARD_COUNT_ENV} is set"
        )

    logger.warning(
        "Shard count is not configured, falling back to the default",
        num_shards=default,
        set_instead=SHARD_COUNT_ENV,
    )
    return ShardCount(default, "default")


async def register_shard_count(
    redis: "Redis", service: str, count: int
) -> dict[str, int]:
    """Publish this service's shard count and shout if the others disagree.

    The invariant is cross-service, so no single service can validate it from
    its own config alone. Each one records what it booted with, reads back what
    everyone else recorded, and logs an error when they are not all the same.
    That turns the failure mode this exists for — rest_api publishing on
    `% 16` while only shards 0 and 1 are leased, losing seven eighths of every
    REST-published event with nothing in the logs — into one loud line at
    startup.

    A mismatch is expected and harmless *during* a rolling deploy that changes
    the number; it is a bug if it persists.

    Diagnostics must never keep a service from starting, so Redis failures here
    are logged and swallowed rather than raised. That is the deliberate
    exception to the "do not log and fall through" convention, not a licence to
    copy it into delivery code.
    """
    try:
        await redis.hset(SHARD_COUNT_KEY, service, count)
        # Bounded so a long-dead deployment's entries cannot haunt a new one.
        # Every service refreshes it on boot.
        await redis.expire(SHARD_COUNT_KEY, SHARD_COUNT_TTL_SECONDS)
        raw = await redis.hgetall(SHARD_COUNT_KEY)
    except Exception:
        logger.exception("Could not check shard count agreement", service=service)
        return {}

    reported = {_text(name): int(value) for name, value in raw.items()}

    if len(set(reported.values())) > 1:
        logger.error(
            "Services disagree on the shard count: events published to a shard "
            "nobody leases are discarded silently",
            service=service,
            num_shards=count,
            reported=reported,
        )
    else:
        logger.info("Shard count agreed", service=service, num_shards=count)

    return reported


def _text(value) -> str:
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)
