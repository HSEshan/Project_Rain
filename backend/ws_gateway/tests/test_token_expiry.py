"""A socket must not outlive its access token, and its routes must not die first.

Until 2026-11-28 `user:{id}:grpc_endpoint` was written with a TTL equal to the
access token's remaining life, and `reassert_routes` stopped refreshing it once
the token had expired. Nothing closed the socket at `exp`. So an hour after
connecting, a still-open socket silently lost every user-addressed event,
`channels_changed` included, and a user kicked from a guild kept receiving its
messages: the gateway never heard that the membership had gone.

The fix has two halves, one test class each:

- the user route has a fixed TTL and is reasserted for as long as a socket is
  held, independent of any token;
- the endpoint closes the socket with 1008 at the token's `exp`, which the
  client answers by renewing and reconnecting.

Real time, not a fake clock: tokens here expire a second or two out, so the
module takes a few seconds.

    cd backend/ws_gateway && python -m unittest discover -s tests
"""

import asyncio
import sys
import time
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jose import jwt  # noqa: E402
from libs.event.schema import (  # noqa: E402
    CHANNELS_CHANGED_FLAG,
    Event,
    EventType,
    TargetType,
)
from src.api.router import websocket_endpoint  # noqa: E402
from src.auth.models import CurrentUser  # noqa: E402
from src.core.config import settings  # noqa: E402
from src.event.event_dispatcher import EventDispatcher  # noqa: E402
from src.websocket.manager import websocket_manager  # noqa: E402
from test_routing_race import ENDPOINT, FakeRedis, make_manager  # noqa: E402

# Real ids: Event validates them, unlike the routing-race fakes
USER = str(uuid4())
MODERATOR = str(uuid4())
CHANNELS = [str(uuid4()) for _ in range(4)]

GUILD_CHANNEL = CHANNELS[0]


class ExpiringRedis(FakeRedis):
    """FakeRedis whose user route honours its TTL, like SETEX does."""

    def __init__(self, channels):
        super().__init__(channels)
        self.user_route_deadline: dict[str, float] = {}

    async def set_user_grpc_endpoint(self, user_id, endpoint, ttl=None):
        await super().set_user_grpc_endpoint(user_id, endpoint, ttl)
        self.user_route_deadline[user_id] = time.monotonic() + ttl

    def user_route(self, user_id):
        if time.monotonic() >= self.user_route_deadline.get(user_id, 0):
            return None
        return self.user_endpoints.get(user_id)


class RecordingSocket:
    def __init__(self):
        self.sent = []
        self.closed_with = None
        self._closed = asyncio.Event()

    async def accept(self):
        await asyncio.sleep(0)

    async def send_json(self, data):
        self.sent.append(data)

    async def receive_text(self):
        # A tab left open: the client never sends anything
        await self._closed.wait()

    async def close(self, code=1000, reason=None):
        self.closed_with = code
        self._closed.set()


def user_expiring_in(seconds):
    return CurrentUser(
        id=USER,
        email="someone@example.test",
        name="someone",
        exp=int(time.time()) + seconds,
    )


async def sleep_past(exp):
    await asyncio.sleep(max(exp - time.time(), 0) + 0.5)


def consumer_delivers(redis, dispatcher, event):
    """What event_consumer does: route by Redis, or drop. True if delivered."""
    if event.target_type is TargetType.USER:
        routed = redis.user_route(event.target_id) == ENDPOINT
    else:
        routed = ENDPOINT in redis.channel_endpoints.get(event.target_id, set())
    if not routed:
        return False
    return dispatcher.send_events_to_clients([event])


def guild_message():
    return Event(
        event_type=EventType.MESSAGE,
        sender_id=MODERATOR,
        target_type=TargetType.CHANNEL,
        target_id=GUILD_CHANNEL,
        text="still here?",
    )


def kicked_notice():
    return Event(
        event_type=EventType.NOTIFICATION,
        sender_id=MODERATOR,
        target_type=TargetType.USER,
        target_id=USER,
        text="",
        metadata={CHANNELS_CHANGED_FLAG: True},
    )


class UserRouteOutlivesToken(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.redis = ExpiringRedis(CHANNELS)
        self.manager = make_manager(self.redis)
        self.dispatcher = EventDispatcher()
        self.dispatcher.set_websocket_manager(self.manager)
        self.socket = RecordingSocket()
        self.user = user_expiring_in(1)
        await self.manager.add_client(self.user, self.socket)

    async def test_route_ttl_is_not_the_token_lifetime(self):
        remaining = self.redis.user_route_deadline[USER] - time.monotonic()
        self.assertGreater(remaining, 30)

    async def test_reassert_keeps_the_user_route_past_token_expiry(self):
        await sleep_past(self.user.exp)
        await self.manager.reassert_routes()

        self.assertEqual(self.redis.user_route(USER), ENDPOINT)

    async def test_a_kick_after_token_expiry_stops_delivery(self):
        await sleep_past(self.user.exp)
        await self.manager.reassert_routes()

        # rest_api deletes the membership, then publishes channels_changed
        self.redis.channels = [c for c in CHANNELS if c != GUILD_CHANNEL]
        delivery = consumer_delivers(self.redis, self.dispatcher, kicked_notice())
        self.assertTrue(delivery, "channels_changed was dropped by the consumer")
        await delivery

        sent_before = len(self.socket.sent)
        delivery = consumer_delivers(self.redis, self.dispatcher, guild_message())
        if delivery:
            await delivery
        self.assertEqual(
            len(self.socket.sent), sent_before, "kicked user still got the message"
        )


class SocketClosesAtTokenExpiry(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.redis = ExpiringRedis(CHANNELS)
        websocket_manager.set_grpc_endpoint(ENDPOINT)
        websocket_manager.set_redis_manager(self.redis)

    async def asyncTearDown(self):
        websocket_manager.clients.clear()
        websocket_manager.redis_manager = None

    def token(self, exp):
        payload = {"sub": "someone@example.test", "name": "someone", "id": USER}
        payload["exp"] = exp
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    async def test_idle_socket_is_closed_with_1008_and_unrouted(self):
        exp = int(time.time()) + 2
        socket = RecordingSocket()

        try:
            await asyncio.wait_for(
                websocket_endpoint(socket, self.token(exp)),
                timeout=exp - time.time() + 2,
            )
        except TimeoutError:
            self.fail("socket was still open two seconds after its token expired")

        self.assertEqual(socket.closed_with, 1008)
        self.assertGreaterEqual(time.time(), exp)
        self.assertNotIn(USER, websocket_manager.clients)
        self.assertNotIn(USER, self.redis.user_endpoints)
        self.assertEqual(self.redis.channel_endpoints, {})


if __name__ == "__main__":
    unittest.main()
