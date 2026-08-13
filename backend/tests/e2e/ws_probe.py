"""Websocket half of the end-to-end smoke test.

Runs *inside* the ws_gateway container (it needs the `websockets` package and
the compose network), driven by `smoke.py`. Takes the fixture JSON as argv[1].
"""

import asyncio
import json
import sys
import urllib.request

import websockets

ctx = json.loads(sys.argv[1])
GATEWAY = "ws://ws_gateway:8000/?token="
CHANNEL = ctx["channel_id"]
TEXT = ctx["text"]


async def main() -> int:
    async with websockets.connect(GATEWAY + ctx["receiver"]["token"]) as receiver:
        async with websockets.connect(GATEWAY + ctx["sender"]["token"]) as sender:
            # both sockets must be registered in redis before the send
            await asyncio.sleep(1)
            await sender.send(
                json.dumps(
                    {"event_type": "message", "receiver_id": CHANNEL, "text": TEXT}
                )
            )
            try:
                raw = await asyncio.wait_for(receiver.recv(), timeout=10)
            except asyncio.TimeoutError:
                print("  FAIL  second client received the message (timed out)")
                return 1

    event = json.loads(raw)
    delivered = event.get("text") == TEXT and event.get("receiver_id") == CHANNEL
    report("second client received the message", delivered, event)

    await asyncio.sleep(1)  # the gateway persists in batches
    req = urllib.request.Request(
        f"http://rest_api:8000/messages/{CHANNEL}",
        headers={"Authorization": f"Bearer {ctx['receiver']['token']}"},
    )
    with urllib.request.urlopen(req) as resp:
        history = json.loads(resp.read().decode())

    persisted = [m for m in history if m["content"] == TEXT]
    report("message persisted to postgres", bool(persisted), history)

    # the frontend dedupes REST history against live events on this id
    same_id = bool(persisted) and persisted[0]["id"] == event.get("event_id")
    report("stored message id equals ws event_id", same_id)

    return 0 if (delivered and persisted and same_id) else 1


def report(name: str, ok: bool, detail=None) -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'' if ok else f' {detail}'}")


sys.exit(asyncio.run(main()))
