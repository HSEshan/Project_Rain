"""The websocket's message limit, end to end.

Runs inside the ws_gateway container, driven by `rate_limit_probe.py`, against a
stack started with RATE_LIMIT_ENABLED=true. Takes the fixture JSON as argv[1].
"""

import asyncio
import json
import sys
import uuid

import websockets

ctx = json.loads(sys.argv[1])
GATEWAY = "ws://ws_gateway:8000/?token="
sender, other = ctx["sender"], ctx["other"]
CHANNEL = ctx["channel_id"]
failures = 0


def report(name, ok, detail=""):
    global failures
    if ok:
        print(f"  PASS  {name}")
    else:
        failures += 1
        print(f"  FAIL  {name} {detail}")


async def frames(socket, seconds):
    received = []
    try:
        async with asyncio.timeout(seconds):
            while True:
                received.append(json.loads(await socket.recv()))
    except TimeoutError:
        pass
    return received


async def main() -> int:
    tag = uuid.uuid4().hex
    async with (
        websockets.connect(GATEWAY + sender["token"]) as sender_ws,
        websockets.connect(GATEWAY + other["token"]) as other_ws,
    ):
        await asyncio.sleep(1)
        for index in range(30):
            await sender_ws.send(
                json.dumps(
                    {
                        "event_type": "message",
                        "receiver_id": CHANNEL,
                        "text": f"{tag} {index}",
                    }
                )
            )

        at_sender = await frames(sender_ws, 3)
        refusals = [
            f
            for f in at_sender
            if (f.get("metadata") or {}).get("action") == "rate_limited"
        ]
        report("a flood gets a rate_limited frame", len(refusals) == 10, str(len(refusals)))
        report(
            "the frame says how long to wait",
            bool(refusals) and refusals[0]["metadata"].get("retry_after", 0) >= 1,
            str(refusals[:1]),
        )

        at_other = await frames(other_ws, 1)
        delivered = [f for f in at_other if str(f.get("text", "")).startswith(tag)]
        report(
            "exactly the limit gets through",
            len(delivered) == 20,
            f"{len(delivered)} delivered",
        )
        report(
            "the refusal goes only to the socket that sent too fast",
            not [
                f
                for f in at_other
                if (f.get("metadata") or {}).get("action") == "rate_limited"
            ],
        )

        # The limit is on the sender, so someone else in the channel is unaffected
        unaffected = f"{tag} other"
        await other_ws.send(
            json.dumps(
                {"event_type": "message", "receiver_id": CHANNEL, "text": unaffected}
            )
        )
        received = await frames(sender_ws, 2)
        report(
            "another sender is not limited",
            [f for f in received if f.get("text") == unaffected],
        )

    return 1 if failures else 0


sys.exit(asyncio.run(main()))
