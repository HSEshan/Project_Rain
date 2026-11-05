"""What a hostile client can make the websocket do.

Runs inside the ws_gateway container, driven by `smoke.py`, like the other
probes. Takes the fixture JSON as argv[1]. Everything here is something the UI
never sends, which is the point: the socket builds an `Event` straight from the
client's JSON, so every field in it is attacker-supplied, and the first of these
checks was a live hole until 2026-11-04.
"""

import asyncio
import json
import sys
import urllib.error
import urllib.request
import uuid

import websockets

ctx = json.loads(sys.argv[1])
GATEWAY = "ws://ws_gateway:8000/?token="
alice, bob, mallory = ctx["alice"], ctx["bob"], ctx["mallory"]
CHANNEL = ctx["channel_id"]
failures = 0


def report(name, ok, detail=""):
    global failures
    if ok:
        print(f"  PASS  {name}")
    else:
        failures += 1
        print(f"  FAIL  {name} {detail}")


def history(token):
    req = urllib.request.Request(f"http://rest_api:8000/messages/{CHANNEL}")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


async def frames(socket, seconds):
    """Everything this socket receives in the next few seconds."""
    received = []
    try:
        async with asyncio.timeout(seconds):
            while True:
                received.append(json.loads(await socket.recv()))
    except TimeoutError:
        pass
    return received


async def main() -> int:
    async with (
        websockets.connect(GATEWAY + alice["token"]) as alice_ws,
        websockets.connect(GATEWAY + bob["token"]) as bob_ws,
        websockets.connect(GATEWAY + mallory["token"]) as mallory_ws,
    ):
        await asyncio.sleep(1)

        # 1. a stranger writing into someone else's conversation
        intrusion = f"intrusion {uuid.uuid4().hex}"
        await mallory_ws.send(
            json.dumps(
                {"event_type": "message", "receiver_id": CHANNEL, "text": intrusion}
            )
        )
        received = await frames(alice_ws, 2)
        report(
            "a non-member's message is not delivered to the channel",
            not [f for f in received if f.get("text") == intrusion],
            str(received),
        )
        report(
            "a non-member's message is not stored",
            not [m for m in history(alice["token"]) if m["content"] == intrusion],
        )

        # 2. forged system events, addressed straight at a user or a channel
        forged = f"forged {uuid.uuid4().hex}"
        for event in (
            {"event_type": "notification", "receiver_id": alice["id"], "text": forged},
            {"event_type": "friend_request", "receiver_id": alice["id"], "text": forged},
            {"event_type": "voice_state", "receiver_id": CHANNEL, "text": forged},
            {"event_type": "call", "receiver_id": CHANNEL, "text": forged},
        ):
            await mallory_ws.send(json.dumps(event))
            await bob_ws.send(json.dumps(event))
        received = await frames(alice_ws, 2)
        report(
            "a client cannot forge a non-message event",
            not [f for f in received if f.get("text") == forged],
            str(received),
        )

        # 3. poison: events built to fail the shared batch transaction. Sent
        # back to back with a real message so that they land in one batch.
        honest = f"honest {uuid.uuid4().hex}"
        existing = history(alice["token"])[0]["id"]
        poison = [
            # duplicate primary key
            {"event_type": "message", "receiver_id": CHANNEL, "text": "x", "event_id": existing},
            # not a uuid
            {"event_type": "message", "receiver_id": CHANNEL, "text": "x", "event_id": "nope"},
            # channel-addressed type claiming to be user-addressed
            {"event_type": "message", "target_type": "user", "target_id": alice["id"], "text": "x"},
            # not a uuid, as a channel
            {"event_type": "message", "receiver_id": "nope", "text": "x"},
            # a NUL cannot be stored in a Postgres text column
            {"event_type": "message", "receiver_id": CHANNEL, "text": "a\u0000b"},
        ]
        for attempt in poison:
            await bob_ws.send(json.dumps(attempt))
        await alice_ws.send(
            json.dumps({"event_type": "message", "receiver_id": CHANNEL, "text": honest})
        )
        received = await frames(bob_ws, 2)
        report(
            "a malformed event does not take an honest message down with it",
            [f for f in received if f.get("text") == honest]
            and [m for m in history(alice["token"]) if m["content"] == honest],
            str(received),
        )

        # 4. the size of one message
        oversized = "x" * ctx["max_message_length"] + "x"
        await bob_ws.send(
            json.dumps({"event_type": "message", "receiver_id": CHANNEL, "text": oversized})
        )
        await asyncio.sleep(1)
        report(
            "a message over the length limit is not stored",
            not [m for m in history(alice["token"]) if m["content"] == oversized],
        )

        # Far past the frame limit, on a socket of its own: the gateway closes it
        async with websockets.connect(GATEWAY + mallory["token"], max_size=None) as big:
            await big.send(json.dumps({"event_type": "message", "text": "x" * 200_000}))
            try:
                await asyncio.wait_for(big.recv(), timeout=5)
                closed = False
            except websockets.ConnectionClosed:
                closed = True
            except TimeoutError:
                closed = False
        report("an oversized frame closes the socket", closed)

        # 5. after all of that, the socket still works
        after = f"after {uuid.uuid4().hex}"
        await bob_ws.send(
            json.dumps({"event_type": "message", "receiver_id": CHANNEL, "text": after})
        )
        received = await frames(alice_ws, 2)
        report(
            "the channel still works afterwards",
            [f for f in received if f.get("text") == after],
            str(received),
        )

    return 1 if failures else 0


sys.exit(asyncio.run(main()))
