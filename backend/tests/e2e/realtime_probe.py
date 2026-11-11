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
import uuid

import websockets

ctx = json.loads(sys.argv[1])
GATEWAY = "ws://ws_gateway:8000/?token="
REST = "http://rest_api:8000"

alice = ctx["alice"]
bob = ctx["bob"]
# Group DMs need more than two people, and the "you can only add a friend" rule
# means every one of them has to be reachable to accept a request.
carol = ctx["carol"]
dave = ctx["dave"]
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


def tiny_png(width=16, height=16) -> bytes:
    """A valid PNG from the stdlib alone; this container has no Pillow."""
    import struct
    import zlib

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    rows = b"".join(b"\x00" + b"\x20\x90\xd0" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def upload(path, token):
    """PUT a tiny PNG as the multipart `file` field. Returns (status, body)."""
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"probe.png\"\r\nContent-Type: image/png\r\n\r\n"
    ).encode() + tiny_png() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(REST + path, data=body, method="PUT")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


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
    # Three sockets, all opened before any of the channels below exist.
    # That is the point: every check here is about a client that did not
    # reconnect.
    async with (
        websockets.connect(GATEWAY + alice["token"]) as alice_ws,
        websockets.connect(GATEWAY + bob["token"]) as bob_ws,
        websockets.connect(GATEWAY + carol["token"]) as carol_ws,
    ):
        alice_client = Client(alice_ws)
        bob_client = Client(bob_ws)
        carol_client = Client(carol_ws)
        await asyncio.sleep(1)  # let the sockets register

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

        # 2b. an avatar change reaches everyone who shares a channel, and only them.
        # Carol shares nothing with alice yet; she is the negative case.
        def avatar_event(url):
            return lambda e: (e.get("metadata") or {}).get(
                "action"
            ) == "user_updated" and (e.get("metadata") or {}).get(
                "user_id"
            ) == alice["id"] and (e.get("metadata") or {}).get("avatar_url") == url

        status, profile = upload("/users/me/avatar", alice["token"])
        new_url = profile.get("avatar_url") if isinstance(profile, dict) else None
        report("avatar upload for the realtime check", status == 200 and bool(new_url), str(profile))
        report(
            "an avatar change reaches a friend with its new url",
            await bob_client.wait_for(avatar_event(new_url)) is not None,
        )
        report(
            "an avatar change reaches the actor's own sockets",
            await alice_client.wait_for(avatar_event(new_url)) is not None,
        )
        report(
            "an avatar change does not reach a stranger",
            await carol_client.wait_for(action_is("user_updated"), timeout=1.5) is None,
        )
        call("DELETE", "/users/me/avatar", token=alice["token"])
        report(
            "clearing an avatar is delivered as a null url",
            await bob_client.wait_for(avatar_event(None)) is not None,
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

        # 4. creating a guild makes its default channels live for the
        # creator. Their socket connected before those channels existed, so
        # without an event the gateway has no mapping for them and the
        # first message sent there is persisted and then dropped.
        status, guild = call(
            "POST",
            "/guilds/",
            {"name": "Realtime Guild", "description": "probe"},
            token=alice["token"],
        )
        guild_id = guild["id"]

        event = await alice_client.wait_for(action_is("channels_changed"))
        report("guild creation delivered to its creator", event is not None)

        status, alice_channels = call("GET", "/channels/me", token=alice["token"])
        creator_text = next(
            c["id"]
            for c in alice_channels
            if c.get("guild_id") == guild_id and c["name"] == "general-text"
        )
        await asyncio.sleep(1)
        await alice_ws.send(
            json.dumps(
                {
                    "event_type": "message",
                    "receiver_id": creator_text,
                    "text": "first message in a brand new guild",
                }
            )
        )
        event = await alice_client.wait_for(
            lambda e: e.get("text") == "first message in a brand new guild"
        )
        report(
            "creator's first message in a new guild comes back without a reload",
            event is not None,
        )
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

        # 8. declining an invite is published back to the decliner, so a
        # second tab of theirs drops the offer it is still showing. It is
        # not a membership change, so it must not claim channels_changed.
        status, second_guild = call(
            "POST",
            "/guilds/",
            {"name": "Declined Guild", "description": "probe"},
            token=alice["token"],
        )
        status, declinable = call(
            "POST",
            f"/guilds/{second_guild['id']}/invite",
            {"user_id": bob["id"]},
            token=alice["token"],
        )
        event = await bob_client.wait_for(
            lambda e: (e.get("metadata") or {}).get("invite_id")
            == declinable["invite_id"]
            and (e.get("metadata") or {}).get("action") == "guild_invite_received"
        )
        report("second guild invite delivered over ws", event is not None)

        call(
            "DELETE",
            f"/guilds/{second_guild['id']}/invites/{declinable['invite_id']}",
            token=bob["token"],
        )
        event = await bob_client.wait_for(action_is("guild_invite_removed"))
        report("declining an invite is delivered to the decliner", event is not None)
        report(
            "declining does not claim a membership change",
            event is not None
            and not (event.get("metadata") or {}).get("channels_changed"),
            str(event),
        )

        # 8b. guild changes. Its own guild, because the last step deletes it.
        # Bob stays in the guild through a rename and a role change, so neither
        # may claim a membership change; the two deletes do change his.
        status, roles_guild = call(
            "POST",
            "/guilds/",
            {"name": "Probe roles", "description": "probe"},
            token=alice["token"],
        )
        roles_guild_id = roles_guild["id"]
        status, roles_invite = call(
            "POST",
            f"/guilds/{roles_guild_id}/invite",
            {"user_id": bob["id"]},
            token=alice["token"],
        )
        await bob_client.wait_for(
            lambda e: (e.get("metadata") or {}).get("invite_id")
            == roles_invite["invite_id"]
        )
        call(
            "POST",
            f"/guilds/{roles_guild_id}/invites/{roles_invite['invite_id']}/accept",
            token=bob["token"],
        )
        event = await alice_client.wait_for(
            lambda e: (e.get("metadata") or {}).get("action") == "guild_updated"
            and (e.get("metadata") or {}).get("guild_id") == roles_guild_id
        )
        report("a join is delivered to the guild's other members", event is not None)
        await bob_client.wait_for(
            lambda e: (e.get("metadata") or {}).get("guild_id") == roles_guild_id
            and (e.get("metadata") or {}).get("channels_changed")
        )

        def guild_updated(guild_id):
            return lambda e: (e.get("metadata") or {}).get(
                "action"
            ) == "guild_updated" and (e.get("metadata") or {}).get(
                "guild_id"
            ) == guild_id

        call(
            "PATCH",
            f"/guilds/{roles_guild_id}",
            {"name": "Probe renamed"},
            token=alice["token"],
        )
        event = await bob_client.wait_for(guild_updated(roles_guild_id))
        report("a rename is delivered to members", event is not None)
        report(
            "a rename does not claim a membership change",
            event is not None
            and not (event.get("metadata") or {}).get("channels_changed"),
            str(event),
        )

        call(
            "PATCH",
            f"/guilds/{roles_guild_id}/members/{bob['id']}",
            {"role": "moderator"},
            token=alice["token"],
        )
        event = await bob_client.wait_for(guild_updated(roles_guild_id))
        report("a role change is delivered to the member", event is not None)

        status, _ = upload(f"/guilds/{roles_guild_id}/icon", alice["token"])
        event = await bob_client.wait_for(
            lambda e: guild_updated(roles_guild_id)(e) and "icon" in e.get("text", "")
        )
        report(
            "a new guild icon is delivered to members",
            status == 200 and event is not None,
            f"{status} {event}",
        )

        status, roles_channels = call("GET", "/channels/me", token=bob["token"])
        doomed = [
            c for c in roles_channels if c.get("guild_id") == roles_guild_id
        ][0]
        call("DELETE", f"/channels/{doomed['id']}", token=alice["token"])
        event = await bob_client.wait_for(
            lambda e: (e.get("metadata") or {}).get("channel_id") == doomed["id"]
        )
        report(
            "a deleted channel is delivered as a membership change",
            event is not None and (event.get("metadata") or {}).get("channels_changed"),
            str(event),
        )

        call("DELETE", f"/guilds/{roles_guild_id}", token=alice["token"])
        event = await bob_client.wait_for(
            lambda e: (e.get("metadata") or {}).get("guild_id") == roles_guild_id
            and (e.get("metadata") or {}).get("channels_changed")
        )
        report("a deleted guild is delivered to its members", event is not None)

        # 8c. a message changing after it was delivered. Fan-out is by channel,
        # like the message itself, and a client must not take it for a new one.
        marker = f"editable {uuid.uuid4().hex}"
        await alice_ws.send(
            json.dumps(
                {"event_type": "message", "receiver_id": dm_channel_id, "text": marker}
            )
        )
        event = await bob_client.wait_for(lambda e: e.get("text") == marker)
        report("a message to edit is delivered", event is not None)
        message_id = event["event_id"]

        status, edited = call(
            "PATCH",
            f"/messages/{message_id}",
            {"content": marker + " v2"},
            token=alice["token"],
        )
        event = await bob_client.wait_for(
            lambda e: (e.get("metadata") or {}).get("action") == "message_edited"
        )
        report(
            "an edit is delivered to the channel",
            event is not None
            and event["event_type"] == "message_update"
            and event["text"] == marker + " v2"
            and event["metadata"]["message_id"] == message_id
            and bool(event["metadata"].get("edited_at")),
            str(event),
        )

        call("DELETE", f"/messages/{message_id}", token=alice["token"])
        event = await bob_client.wait_for(
            lambda e: (e.get("metadata") or {}).get("action") == "message_deleted"
        )
        report(
            "a deletion is delivered to the channel",
            event is not None and event["metadata"]["message_id"] == message_id,
            str(event),
        )

        # 9. group DMs. Three sockets that all connected before the channel
        # existed, which is the same seam guild creation exercises: without
        # an event the gateway holds no mapping for the new channel and the
        # first message sent there is persisted and then dropped.
        call(
            "POST",
            f"/friendship/friends/request?to_username={carol['username']}",
            token=alice["token"],
        )
        status, carol_requests = call(
            "GET", "/friendship/friends/request/me", token=carol["token"]
        )
        call(
            "POST",
            f"/friendship/friends/request/{carol_requests[0]['id']}/accept",
            token=carol["token"],
        )

        status, group = call(
            "POST",
            "/channels/group",
            {"user_ids": [bob["id"], carol["id"]], "name": "Probe group"},
            token=alice["token"],
        )
        group_id = group["id"]

        def channels_changed_for(channel_id):
            return lambda e: (e.get("metadata") or {}).get(
                "action"
            ) == "channels_changed" and (e.get("metadata") or {}).get(
                "channel_id"
            ) == channel_id

        report(
            "group dm creation delivered to a member",
            await bob_client.wait_for(channels_changed_for(group_id)) is not None,
        )
        report(
            "group dm creation delivered to every member",
            await carol_client.wait_for(channels_changed_for(group_id)) is not None,
        )

        await asyncio.sleep(1)
        await alice_ws.send(
            json.dumps(
                {
                    "event_type": "message",
                    "receiver_id": group_id,
                    "text": "first message in a brand new group",
                }
            )
        )
        report(
            "a brand new group dm is live for its members without a reload",
            await bob_client.wait_for(
                lambda e: e.get("text") == "first message in a brand new group"
            )
            is not None,
        )

        # A rename is not a membership change. It must reach the members so
        # their sidebar stops showing the old name, and it must *not* claim
        # channels_changed, which would make the gateway re-read routing and
        # every client rebuild a channel list that did not move.
        def group_updated(e):
            metadata = e.get("metadata") or {}
            return (
                metadata.get("action") == "group_dm_updated"
                and metadata.get("channel_id") == group_id
            )

        call(
            "PATCH",
            f"/channels/{group_id}",
            {"name": "Renamed by the probe"},
            token=alice["token"],
        )
        event = await bob_client.wait_for(group_updated)
        report("group dm rename delivered over ws", event is not None)
        report(
            "a rename does not claim a membership change",
            event is not None
            and not (event.get("metadata") or {}).get("channels_changed"),
            str(event),
        )

        # Adding someone tells the newcomer their channels changed and tells
        # the room its roster moved. Two different facts, two different
        # events, on purpose.
        status, dave_requests = call(
            "POST",
            f"/friendship/friends/request?to_username={dave['username']}",
            token=alice["token"],
        )
        status, dave_requests = call(
            "GET", "/friendship/friends/request/me", token=dave["token"]
        )
        call(
            "POST",
            f"/friendship/friends/request/{dave_requests[0]['id']}/accept",
            token=dave["token"],
        )
        call(
            "POST",
            f"/channels/{group_id}/members",
            {"user_id": dave["id"]},
            token=alice["token"],
        )
        report(
            "adding a member is announced to the room",
            await carol_client.wait_for(group_updated) is not None,
        )

        call("DELETE", f"/channels/{group_id}/members/me", token=alice["token"])
        report(
            "leaving is announced to the room",
            await bob_client.wait_for(
                lambda e: group_updated(e) and "left" in e.get("text", "")
            )
            is not None,
        )
        report(
            "the leaver's own channel list is invalidated",
            await alice_client.wait_for(channels_changed_for(group_id)) is not None,
        )

        alice_client.stop()
        bob_client.stop()
        carol_client.stop()

    return 1 if FAILURES else 0


sys.exit(asyncio.run(main()))
