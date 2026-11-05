"""A fixed-window counter in Redis, shared by rest_api and ws_gateway.

In Redis rather than in the process because rest_api can run as more than one,
and a counter per process is a limit that quietly multiplies by the worker count.

Fixed window on purpose. It lets a client spend up to twice the limit across a
window boundary, which is fine for what this is for: stopping a script, not
metering a customer. A sliding window costs a sorted set per identity to shave a
burst nobody here cares about.

**A Redis failure allows the request.** The alternative is that an outage of the
thing counting requests also takes down sign-in, which is a much bigger outage
than the abuse it would have prevented. It is logged, and nothing is silently
unlimited for longer than Redis is down.
"""

from dataclasses import dataclass

import structlog
from libs.rediskeys import RediKeys
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger()

# One round trip, and atomic: an INCR and an EXPIRE sent separately leave a key
# with no expiry if the client dies between them, and that identity is then
# locked out for good.
_HIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""


@dataclass(frozen=True)
class RateLimit:
    """`limit` hits per `window_seconds`, for one identity. `name` keys the
    counter, so two rules must not share one."""

    name: str
    limit: int
    window_seconds: int


@dataclass(frozen=True)
class Decision:
    allowed: bool
    # Seconds until the window ends. Only meaningful when refused.
    retry_after: int = 0


ALLOWED = Decision(allowed=True)


async def hit(redis: Redis | None, rule: RateLimit, identity: str) -> Decision:
    """Count one request against `rule` for `identity`, and say if it may proceed."""
    if redis is None:
        return ALLOWED
    key = RediKeys.rate_limit(rule.name, identity)
    try:
        count, ttl = await redis.eval(_HIT_SCRIPT, 1, key, rule.window_seconds)
    except (RedisError, OSError):
        logger.warning("Rate limiter unavailable, allowing request", rule=rule.name)
        return ALLOWED
    if count > rule.limit:
        return Decision(allowed=False, retry_after=max(int(ttl), 1))
    return ALLOWED
