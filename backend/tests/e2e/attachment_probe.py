"""Websocket half of the upload checks: claiming attachments with a message.

Runs *inside* the ws_gateway container, driven by `smoke.py`, like ws_probe.py.
The fixture carries two users who share a DM and one attachment uploaded by
the first of them.

What it pins down:

- a message claims the sender's own upload, and every recipient gets it as a
  full attachment object in `metadata.attachments`
- a message can NOT claim someone else's upload, even with the id in hand:
  the gateway checks the uploader, since the ids come from a client
- an upload is claimed once; the same id in a second message attaches nothing
- metadata a client makes up (here `channels_changed`, which the gateway acts
  on) never reaches anyone
- the stored message returns its attachment from the history endpoint
"""

import asyncio
import json
import sys
import urllib.request

import websockets

ctx = json.loads(sys.argv[1])
GATEWAY = "ws://ws_gateway:8000/?token="
CHANNEL = ctx["channel_id"]
OWNER, OTHER = ctx["owner"], ctx["other"]
ATTACHMENT = ctx["attachment_id"]
FAILED = []


def report(name: str, ok: bool, detail=None) -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'' if ok else f' {detail}'}")
    if not ok:
        FAILED.append(name)


async def send(sender, text, metadata=None):
    frame = {"event_type": "message", "receiver_id": CHANNEL, "text": text}
    if metadata is not None:
        frame["metadata"] = metadata
    await sender.send(json.dumps(frame))


async def receive(socket, text):
    """The message event with this text, or None after 10 seconds."""
    try:
        while True:
            event = json.loads(await asyncio.wait_for(socket.recv(), timeout=10))
            if event.get("event_type") == "message" and event.get("text") == text:
                return event
    except asyncio.TimeoutError:
        return None


async def main() -> int:
    async with websockets.connect(GATEWAY + OWNER["token"]) as owner:
        async with websockets.connect(GATEWAY + OTHER["token"]) as other:
            await asyncio.sleep(1)  # both sockets registered before any send

            # Someone else's upload first, while it is still unclaimed: the only
            # thing standing between them and it is the uploader check.
            await send(other, "not yours", {"attachment_ids": [ATTACHMENT]})
            event = await receive(owner, "not yours")
            report(
                "another user's upload is not attachable",
                event is not None and event["metadata"]["attachments"] == [],
                event,
            )

            await send(
                owner,
                "with image",
                {"attachment_ids": [ATTACHMENT], "channels_changed": True},
            )
            event = await receive(other, "with image")
            attached = (event or {}).get("metadata", {}).get("attachments", [])
            report(
                "the recipient gets the claimed attachment",
                len(attached) == 1
                and attached[0]["id"] == ATTACHMENT
                and attached[0]["url"].startswith("/media/attachments/"),
                event,
            )
            report(
                "client-supplied metadata is not passed through",
                set((event or {}).get("metadata", {})) == {"attachments"},
                event,
            )

            await send(owner, "again", {"attachment_ids": [ATTACHMENT]})
            event = await receive(other, "again")
            report(
                "an upload is claimed only once",
                event is not None and event["metadata"]["attachments"] == [],
                event,
            )

    await asyncio.sleep(1)  # the gateway persists in batches
    request = urllib.request.Request(
        f"http://rest_api:8000/messages/{CHANNEL}",
        headers={"Authorization": f"Bearer {OTHER['token']}"},
    )
    history = json.loads(urllib.request.urlopen(request).read().decode())
    stored = [m for m in history if m["content"] == "with image"]
    report(
        "history returns the attachment",
        bool(stored) and [a["id"] for a in stored[-1]["attachments"]] == [ATTACHMENT],
        stored,
    )
    return 1 if FAILED else 0


sys.exit(asyncio.run(main()))
