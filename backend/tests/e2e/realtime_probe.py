"""Realtime half of the end-to-end smoke test.

Runs inside the ws_gateway container (needs `websockets` plus the compose
network). Two users hold open sockets while REST mutations happen, proving that
rest_api -> redis stream -> event_consumer -> gRPC -> socket works, and that a
gateway picks up membership changes without the client reconnecting.

Takes the fixture JSON as argv[1].
"""

import asyncio
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

import websockets

ctx = json.loads(sys.argv[1])
GATEWAY = "ws://ws_gateway:8000/?token="
REST = "http://rest_api:8000"

alice = ctx["alice"]
bob = ctx["bob"]
FAILURES = []


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(REST + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            payload = resp.read().decode()
            return resp.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return e.code, body


def report(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'' if ok else f' {detail}'}")
    if not ok:
        FAILURES.append(name)


class Client:
    """A live socket plus everything it has received so far."""

    def __init__(self, socket):
        self.socket = socket
        self.events = []
        self._task = asyncio.create_task(self._drain())

    async def _drain(self):
        try:
            async for raw in self.socket:
                self.events.append(json.loads(raw))
        except Exception:
            pass

    async def wait_for(self, predicate, timeout=10):
        """Wait for an event matching `predicate`, including ones already seen."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            for event in self.events:
                if predicate(event):
                    return event
            await asyncio.sleep(0.1)
        return None

    def stop(self):
        self._task.cancel()


def action_is(name):
    return lambda event: (event.get("metadata") or {}).get("action") == name


async def main() -> int:
    async with websockets.connect(GATEWAY + alice["token"]) as alice_ws:
        async with websockets.connect(GATEWAY + bob["token"]) as bob_ws:
            alice_client = Client(alice_ws)
            bob_client = Client(bob_ws)
            await asyncio.sleep(1)  # let both sockets register

            # 1. friend request reaches the recipient live
            call(
                "POST",
                f"/friendship/friends/request?to_username={bob['username']}",
                token=alice["token"],
            )
            event = await bob_client.wait_for(action_is("friend_request_received"))
            report("friend request delivered over ws", event is not None)
            request_id = (event or {}).get("metadata", {}).get("request_id")

            # 2. the acceptance reaches the original sender live
            status, accepted = call(
                "GET", "/friendship/friends/request/me", token=bob["token"]
            )
            request_id = request_id or accepted[0]["id"]
            status, accepted = call(
                "POST",
                f"/friendship/friends/request/{request_id}/accept",
                token=bob["token"],
            )
            event = await alice_client.wait_for(action_is("friend_request_accepted"))
            report("friend acceptance delivered over ws", event is not None)
            dm_channel_id = (event or {}).get("metadata", {}).get("dm_channel_id")
            report(
                "acceptance carries the new dm channel",
                dm_channel_id == accepted.get("dm_channel_id"),
                f"{dm_channel_id} != {accepted}",
            )

            # 3. the DM works immediately, without either client reconnecting.
            # Both sockets connected before this channel existed.
            await alice_ws.send(
                json.dumps(
                    {
                        "event_type": "message",
                        "receiver_id": dm_channel_id,
                        "text": "live dm",
                    }
                )
            )
            event = await bob_client.wait_for(
                lambda e: e.get("text") == "live dm" and e.get("event_type") == "message"
            )
            report("new dm channel is live without reconnect", event is not None)

            # 4. guild invite reaches the invited user live
            status, guild = call(
                "POST",
                "/guilds/",
                {"name": "Realtime Guild", "description": "probe"},
                token=alice["token"],
            )
            guild_id = guild["id"]
            status, invite = call(
                "POST",
                f"/guilds/{guild_id}/invite",
                {"user_id": bob["id"]},
                token=alice["token"],
            )
            event = await bob_client.wait_for(action_is("guild_invite_received"))
            report("guild invite delivered over ws", event is not None)

            # 5. accepting the invite tells bob his channels changed
            call(
                "POST",
                f"/guilds/{guild_id}/invites/{invite['invite_id']}/accept",
                token=bob["token"],
            )
            event = await bob_client.wait_for(action_is("channels_changed"))
            report("guild join delivered over ws", event is not None)

            # 6. the payoff: bob joined a guild channel while connected, so the
            # gateway must have refreshed his membership mapping for him to get
            # anything sent there.
            status, channels = call("GET", "/channels/me", token=bob["token"])
            general_text = next(
                c["id"]
                for c in channels
                if c.get("guild_id") == guild_id and c["name"] == "general-text"
            )
            await asyncio.sleep(1)
            await alice_ws.send(
                json.dumps(
                    {
                        "event_type": "message",
                        "receiver_id": general_text,
                        "text": "welcome to the guild",
                    }
                )
            )
            event = await bob_client.wait_for(
                lambda e: e.get("text") == "welcome to the guild"
            )
            report(
                "guild channel is live for a member who joined mid-session",
                event is not None,
            )

            # 7. a new channel created by an admin reaches existing members
            status, new_channel = call(
                "POST",
                f"/channels/guild/{guild_id}",
                {"name": "probe-channel", "type": "guild_text"},
                token=alice["token"],
            )
            event = await bob_client.wait_for(
                lambda e: (e.get("metadata") or {}).get("channel_id")
                == new_channel["id"]
            )
            report("channel creation delivered to guild members", event is not None)

            alice_client.stop()
            bob_client.stop()

    return 1 if FAILURES else 0


sys.exit(asyncio.run(main()))
