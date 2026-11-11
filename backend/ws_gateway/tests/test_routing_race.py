"""A page reload must not unroute the socket that replaces the old one.

A reload is a disconnect and a connect for one user at the same moment. Both
walk the user's channels with an await per Redis call, and before the per-user
lock (2026-09-24) the teardown of the old socket interleaved with the new one's
registration: it removed channel routes the new socket had just added and then
deleted `user:{id}:grpc_endpoint`. The client stayed connected and silently
received nothing. Found because a DM call's "left" event never arrived.

The fake Redis yields on every call, which is what lets the two coroutines
interleave the way real network round trips do. The last test removes the lock
and checks the fake really does reproduce the bug, so the other tests are known
to be able to fail.

    cd backend/ws_gateway && python -m unittest discover -s tests
"""

import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.auth.models import CurrentUser  # noqa: E402
from src.websocket.manager import WebsocketManager  # noqa: E402

ENDPOINT = "gateway-1:6000"
USER = "user-1"
CHANNELS = [f"channel-{n}" for n in range(8)]


class FakeRedis:
    """Just the routing keys, held in memory. Every call yields first."""

    def __init__(self, channels):
        self.channels = list(channels)
        self.user_endpoints: dict[str, str] = {}
        self.channel_endpoints: dict[str, set[str]] = {}

    async def _hop(self):
        await asyncio.sleep(0)

    async def set_user_grpc_endpoint(self, user_id, endpoint, ttl=None):
        await self._hop()
        self.user_endpoints[user_id] = endpoint

    async def delete_user_grpc_endpoint(self, user_id):
        await self._hop()
        self.user_endpoints.pop(user_id, None)

    async def get_user_channel_ids(self, user_id):
        await self._hop()
        return list(self.channels)

    async def delete_user_channels(self, user_id):
        await self._hop()

    async def add_grpc_endpoint_to_channel(self, channel_id, endpoint):
        await self._hop()
        self.channel_endpoints.setdefault(channel_id, set()).add(endpoint)

    async def remove_grpc_endpoint_from_channel(self, channel_id, endpoint):
        await self._hop()
        members = self.channel_endpoints.get(channel_id, set())
        members.discard(endpoint)
        if not members:
            # Redis deletes an empty set on its own
            self.channel_endpoints.pop(channel_id, None)


class FakeSocket:
    async def accept(self):
        await asyncio.sleep(0)


def user():
    # Far-future expiry: only the TTL arithmetic reads it
    return CurrentUser(
        id=USER, email="someone@example.test", name="someone", exp=4_102_444_800
    )


def make_manager(redis):
    manager = WebsocketManager()
    manager.set_grpc_endpoint(ENDPOINT)
    manager.set_redis_manager(redis)
    return manager


def routing_problems(manager, redis, expect_sockets):
    """Everything wrong with the routing for USER, as readable strings."""
    problems = []
    if redis.user_endpoints.get(USER) != ENDPOINT:
        problems.append("user endpoint missing")
    unrouted = [
        channel
        for channel in CHANNELS
        if ENDPOINT not in redis.channel_endpoints.get(channel, set())
    ]
    if unrouted:
        problems.append(f"{len(unrouted)} of {len(CHANNELS)} channels unrouted")
    if manager.clients.get(USER, set()) != expect_sockets:
        problems.append("wrong sockets held")
    return problems


async def reload(manager, old_socket, new_socket):
    """The old tab's close and the new tab's connect, at the same moment."""
    await asyncio.gather(
        manager.remove_client(USER, old_socket),
        manager.add_client(user(), new_socket),
    )


class Reload(unittest.IsolatedAsyncioTestCase):
    async def test_a_reload_keeps_every_route(self):
        redis = FakeRedis(CHANNELS)
        manager = make_manager(redis)
        old, new = FakeSocket(), FakeSocket()
        await manager.add_client(user(), old)

        await reload(manager, old, new)

        self.assertEqual(routing_problems(manager, redis, {new}), [])

    async def test_connect_first_then_close_keeps_every_route(self):
        """The other order: the new socket's connect starts before the close."""
        redis = FakeRedis(CHANNELS)
        manager = make_manager(redis)
        old, new = FakeSocket(), FakeSocket()
        await manager.add_client(user(), old)

        await asyncio.gather(
            manager.add_client(user(), new),
            manager.remove_client(USER, old),
        )

        self.assertEqual(routing_problems(manager, redis, {new}), [])

    async def test_five_rapid_reloads(self):
        redis = FakeRedis(CHANNELS)
        manager = make_manager(redis)
        current = FakeSocket()
        await manager.add_client(user(), current)

        for _ in range(5):
            replacement = FakeSocket()
            await reload(manager, current, replacement)
            current = replacement

        self.assertEqual(routing_problems(manager, redis, {current}), [])

    async def test_a_refresh_during_a_reload_keeps_every_route(self):
        """`channels_changed` can arrive mid-reload; it takes the same lock."""
        redis = FakeRedis(CHANNELS)
        manager = make_manager(redis)
        old, new = FakeSocket(), FakeSocket()
        await manager.add_client(user(), old)

        await asyncio.gather(
            manager.remove_client(USER, old),
            manager.refresh_user_channels(USER),
            manager.add_client(user(), new),
        )

        self.assertEqual(routing_problems(manager, redis, {new}), [])

    async def test_last_socket_closing_does_unroute(self):
        """The lock must not stop a real disconnect from cleaning up."""
        redis = FakeRedis(CHANNELS)
        manager = make_manager(redis)
        only = FakeSocket()
        await manager.add_client(user(), only)

        await manager.remove_client(USER, only)

        self.assertNotIn(USER, redis.user_endpoints)
        self.assertEqual(redis.channel_endpoints, {})
        self.assertNotIn(USER, manager.clients)

    async def test_reassert_restores_routes_removed_behind_its_back(self):
        """What the consumer does when it wrongly decides this gateway is dead."""
        redis = FakeRedis(CHANNELS)
        manager = make_manager(redis)
        socket = FakeSocket()
        await manager.add_client(user(), socket)
        redis.user_endpoints.clear()
        redis.channel_endpoints.clear()

        await manager.reassert_routes()

        self.assertEqual(routing_problems(manager, redis, {socket}), [])

    async def test_reassert_during_a_disconnect_does_not_resurrect_routes(self):
        redis = FakeRedis(CHANNELS)
        manager = make_manager(redis)
        socket = FakeSocket()
        await manager.add_client(user(), socket)

        await asyncio.gather(
            manager.remove_client(USER, socket), manager.reassert_routes()
        )

        self.assertNotIn(USER, redis.user_endpoints)
        self.assertEqual(redis.channel_endpoints, {})

    async def test_the_race_is_real_without_the_lock(self):
        """Without this, the tests above could pass for a reason other than the lock."""
        redis = FakeRedis(CHANNELS)
        manager = make_manager(redis)
        # A fresh lock per call excludes nothing, which is the code before the fix
        manager._lock = lambda user_id: asyncio.Lock()
        old, new = FakeSocket(), FakeSocket()
        await manager.add_client(user(), old)

        await reload(manager, old, new)

        self.assertNotEqual(routing_problems(manager, redis, {new}), [])


if __name__ == "__main__":
    unittest.main()
