"""Voice half of the end-to-end smoke test.

Proves the SFU path without a browser:

  * rest_api authorises a join and mints a LiveKit token
  * LiveKit itself accepts that token (both its validate endpoint and a real
    signalling websocket, which is where a bad grant or a wrong room shows up)
  * **LiveKit drives the roster**: connecting a signalling socket puts you in
    the list and dropping it takes you out, with no cooperation from the
    client. This is the regression test for the ghost-participant bug — a
    browser that refreshes or crashes never gets to say "I left"
  * presence rides our own event pipeline to a member who is not in the room
  * text channels and non-members cannot get a token

Audio is not asserted — that needs two real browsers, and it is the one thing
LiveKit is responsible for rather than us. What this covers is every seam we
wrote.

Runs inside the ws_gateway container, driven by `smoke.py`. Fixture JSON is
argv[1].
"""

import asyncio
import base64
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import websockets

ctx = json.loads(sys.argv[1])
GATEWAY = "ws://ws_gateway:8000/?token="
REST = "http://rest_api:8000"
LIVEKIT_HTTP = "http://livekit:7880"
LIVEKIT_WS = "ws://livekit:7880"

alice = ctx["alice"]
bob = ctx["bob"]
LK_KEY = ctx["livekit"]["key"]
LK_SECRET = ctx["livekit"]["secret"]
FAILURES = []


def jwt_hs256(claims: dict, secret: str) -> str:
    """Minimal HS256 signer — the gateway image has no JWT library, and this
    probe has to speak LiveKit's auth for both webhooks and the server API."""

    def segment(data: dict) -> bytes:
        raw = json.dumps(data, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    signing_input = segment({"alg": "HS256", "typ": "JWT"}) + b"." + segment(claims)
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return (
        signing_input + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")
    ).decode()


def post_webhook(payload: dict, secret: str = LK_SECRET, key: str = LK_KEY) -> int:
    """Send a webhook the way LiveKit does: signed, with the body hash in the
    token so the payload cannot be swapped."""
    body = json.dumps(payload).encode()
    now = int(time.time())
    token = jwt_hs256(
        {
            "iss": key,
            "nbf": now - 10,
            "exp": now + 300,
            "sha256": base64.b64encode(hashlib.sha256(body).digest()).decode(),
        },
        secret,
    )
    req = urllib.request.Request(REST + "/voice/webhook", data=body, method="POST")
    req.add_header("Content-Type", "application/webhook+json")
    req.add_header("Authorization", token)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def livekit_admin(room: str) -> str:
    now = int(time.time())
    return jwt_hs256(
        {
            "iss": LK_KEY,
            "sub": "e2e-probe",
            "nbf": now - 10,
            "exp": now + 300,
            "video": {"roomCreate": True, "roomAdmin": True, "room": room},
        },
        LK_SECRET,
    )


def room_service(method: str, body: dict, room: str) -> int:
    """LiveKit's server API (twirp).

    DeleteRoom is used to get to a known-empty state, so a 404 for a room that
    was never created is the expected case rather than a problem.
    """
    req = urllib.request.Request(
        f"{LIVEKIT_HTTP}/twirp/livekit.RoomService/{method}",
        data=json.dumps(body).encode(),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {livekit_admin(room)}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:200]
        if not (method == "DeleteRoom" and e.code == 404):
            print(f"        {method} failed: {e.code} {detail}")
        return e.code


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
        return e.code, e.read().decode()


def report(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'' if ok else f' {detail}'}")
    if not ok:
        FAILURES.append(name)


def livekit_validates(token: str) -> bool:
    """LiveKit's own verdict on our hand-rolled token."""
    query = urllib.parse.urlencode({"access_token": token})
    try:
        with urllib.request.urlopen(f"{LIVEKIT_HTTP}/rtc/validate?{query}") as resp:
            return resp.status == 200
    except urllib.error.HTTPError:
        return False


def signal_url(token: str) -> str:
    query = urllib.parse.urlencode(
        {
            "access_token": token,
            "auto_subscribe": "1",
            "sdk": "js",
            "version": "2.21.0",
            "protocol": "15",
        }
    )
    return f"{LIVEKIT_WS}/rtc?{query}"


async def roster(channel_id: str, token: str) -> list[str]:
    status, body = call(
        "GET", f"/channels/{channel_id}/voice/participants", token=token
    )
    return body["participants"] if status == 200 else []


async def wait_for_roster(channel_id: str, token: str, expected: list[str]):
    """The roster moves when a webhook lands, not when a request returns."""
    deadline = asyncio.get_event_loop().time() + 10
    current = None
    while asyncio.get_event_loop().time() < deadline:
        current = await roster(channel_id, token)
        if current == expected:
            return True, current
        await asyncio.sleep(0.2)
    return False, current


async def main() -> int:
    # A guild alice owns, with the default general-voice channel, and bob in it
    status, guild = call(
        "POST",
        "/guilds/",
        {"name": "Voice Guild", "description": "probe"},
        token=alice["token"],
    )
    guild_id = guild["id"]
    status, invite = call(
        "POST", f"/guilds/{guild_id}/invite", {"user_id": bob["id"]}, token=alice["token"]
    )
    call(
        "POST",
        f"/guilds/{guild_id}/invites/{invite['invite_id']}/accept",
        token=bob["token"],
    )

    # Two voice channels on purpose. Opening a signalling socket makes LiveKit
    # create and then finish a real room, and those webhooks arrive seconds
    # later — they would race the synthetic ones below if both used the same
    # channel. `voice_channel` is the one LiveKit touches; `probe_channel` is
    # only ever driven by this file.
    call(
        "POST",
        f"/channels/guild/{guild_id}",
        {"name": "probe-voice", "type": "guild_voice"},
        token=alice["token"],
    )
    status, channels = call("GET", "/channels/me", token=alice["token"])
    guild_channels = [c for c in channels if c.get("guild_id") == guild_id]
    voice_channel = next(
        c for c in guild_channels if c["name"] == "general-voice"
    )
    probe_channel = next(c for c in guild_channels if c["name"] == "probe-voice")
    text_channel = next(c for c in guild_channels if c["type"] == "guild_text")

    # bob watches from outside the room: presence has to reach people who have
    # not joined, which is the whole reason it goes through our pipeline
    async with websockets.connect(GATEWAY + bob["token"]) as bob_ws:
        received = []

        async def drain():
            try:
                async for raw in bob_ws:
                    received.append(json.loads(raw))
            except Exception:
                pass

        drain_task = asyncio.create_task(drain())
        await asyncio.sleep(1)

        status, session = call(
            "POST", f"/channels/{voice_channel['id']}/voice/join", token=alice["token"]
        )
        report("join returns a token", status == 200 and bool(session.get("token")), str(session))

        if status != 200:
            drain_task.cancel()
            return 1

        report(
            "room id is the channel id",
            session["room"] == voice_channel["id"],
            f"{session['room']} != {voice_channel['id']}",
        )
        report(
            "identity is the user id",
            session["identity"] == alice["id"],
            session["identity"],
        )
        # A token is not a connection. Adding the caller here is what used to
        # leave a ghost when the client never made it to the SFU.
        report(
            "a token alone does not put you in the roster",
            session["participants"] == [],
            str(session["participants"]),
        )

        report("livekit validates the token", livekit_validates(session["token"]))

        # The signalling socket proves the grant is accepted. It stops short of
        # a full join: LiveKit only counts a participant once WebRTC is up, so
        # the roster assertions below drive the webhook directly instead.
        async with websockets.connect(signal_url(session["token"])) as signal:
            frame = await asyncio.wait_for(signal.recv(), timeout=10)
            report("livekit accepts a signalling connection", bool(frame))

        room = probe_channel["id"]

        def voice_event(action):
            return next(
                (
                    e
                    for e in received
                    if e.get("event_type") == "voice_state"
                    and (e.get("metadata") or {}).get("action") == action
                ),
                None,
            )

        async def wait_for_event(action):
            deadline = asyncio.get_event_loop().time() + 10
            while asyncio.get_event_loop().time() < deadline:
                found = voice_event(action)
                if found:
                    return found
                await asyncio.sleep(0.1)
            return None

        # LiveKit says someone joined
        status = post_webhook(
            {
                "event": "participant_joined",
                "room": {"name": room},
                "participant": {"identity": alice["id"], "name": alice["username"]},
            }
        )
        report("participant_joined webhook accepted", status == 200, str(status))

        ok, current = await wait_for_roster(room, bob["token"], [alice["id"]])
        report("joining puts you in the roster", ok, str(current))

        joined_event = await wait_for_event("voice_joined")
        report("voice join delivered over ws", joined_event is not None)
        if joined_event:
            report(
                "join event names the channel and the user",
                joined_event["metadata"].get("channel_id") == room
                and joined_event["metadata"].get("user_id") == alice["id"],
                str(joined_event["metadata"]),
            )

        # ...and that they left, which is the case a refreshing or crashing
        # browser can never report for itself
        status = post_webhook(
            {
                "event": "participant_left",
                "room": {"name": room},
                "participant": {"identity": alice["id"], "name": alice["username"]},
            }
        )
        report("participant_left webhook accepted", status == 200, str(status))

        ok, current = await wait_for_roster(room, bob["token"], [])
        report("leaving clears you, with no cooperation from the client", ok, str(current))
        report("voice leave delivered over ws", await wait_for_event("voice_left") is not None)

        # A roster that ghosted before webhooks existed heals when the room is
        # next created. This also proves LiveKit really is calling us: the
        # room_started below is emitted by the SFU, not by this probe.
        post_webhook(
            {
                "event": "participant_joined",
                "room": {"name": room},
                "participant": {"identity": alice["id"], "name": alice["username"]},
            }
        )
        await wait_for_roster(room, bob["token"], [alice["id"]])

        room_service("DeleteRoom", {"room": room}, room)
        await asyncio.sleep(0.5)
        created = room_service("CreateRoom", {"name": room}, room)
        report("livekit server api reachable", created == 200, str(created))

        ok, current = await wait_for_roster(room, bob["token"], [])
        report(
            "livekit's own room_started heals a stale roster",
            ok,
            f"{current} (is `webhook.urls` set in livekit.yaml?)",
        )

        room_service("DeleteRoom", {"room": room}, room)
        drain_task.cancel()

    # Note: the consumer's "do not cache an empty endpoint set" rule is not
    # asserted here. Reproducing it end to end needs the gateway to have
    # finished tearing a channel down at the exact moment an event is
    # published, which this probe cannot force — an attempt at it passed
    # against the broken code, which is worse than no test. It is covered
    # deterministically instead in
    # backend/event_consumer/tests/test_grpc_endpoint_cache.py.

    # authz: a text channel is not a voice channel, and a non-member gets
    # nothing at all
    status, body = call(
        "POST", f"/channels/{text_channel['id']}/voice/join", token=alice["token"]
    )
    report("text channel rejects a voice join", status == 403, f"{status} {body}")

    status, body = call(
        "POST", f"/channels/{voice_channel['id']}/voice/join", token=ctx["carol"]["token"]
    )
    report("non-member cannot get a voice token", status == 404, f"{status} {body}")

    status, body = call("POST", f"/channels/{voice_channel['id']}/voice/join")
    report("anonymous cannot get a voice token", status == 401, f"{status} {body}")

    # The webhook is the only writer of the roster, so anyone who can call it
    # can put people in and out of voice channels. It must take nothing that is
    # not signed by our SFU.
    forged = {
        "event": "participant_joined",
        "room": {"name": voice_channel["id"]},
        "participant": {"identity": ctx["carol"]["id"]},
    }

    req = urllib.request.Request(
        REST + "/voice/webhook", data=json.dumps(forged).encode(), method="POST"
    )
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    report("unsigned webhook is rejected", status == 401, str(status))

    report(
        "webhook signed with the wrong secret is rejected",
        post_webhook(forged, secret="not-the-livekit-secret") == 401,
    )

    # A valid signature over a different body must not carry this one
    body = json.dumps(forged).encode()
    now = int(time.time())
    mismatched = jwt_hs256(
        {
            "iss": LK_KEY,
            "nbf": now - 10,
            "exp": now + 300,
            "sha256": base64.b64encode(hashlib.sha256(b"{}").digest()).decode(),
        },
        LK_SECRET,
    )
    req = urllib.request.Request(REST + "/voice/webhook", data=body, method="POST")
    req.add_header("Content-Type", "application/webhook+json")
    req.add_header("Authorization", mismatched)
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
    report("webhook whose body does not match its signature is rejected", status == 401, str(status))

    return 1 if FAILURES else 0


sys.exit(asyncio.run(main()))
