"""One user, several sockets.

The gateway used to hold `user_id -> WebSocket`, so a second tab silently
closed the first. It now holds a set, which means two things have to hold:
every socket gets the event, and closing one must not tear down the user's
routing while another is still open.

Runs inside the ws_gateway container, driven by `smoke.py`. Fixture JSON is
argv[1].
"""

import asyncio
import json
import sys

import websockets

ctx = json.loads(sys.argv[1])
GATEWAY = "ws://ws_gateway:8000/?token="
CHANNEL = ctx["channel_id"]

FAILED = False


def report(name: str, ok: bool, detail=None) -> None:
    global FAILED
    if not ok:
        FAILED = True
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'' if ok else f' {detail}'}")


async def expect(socket, text: str):
    """Wait for `text` on this socket, ignoring anything else in flight."""
    deadline = asyncio.get_running_loop().time() + 10
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return False
        try:
            raw = await asyncio.wait_for(socket.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            return False
        if json.loads(raw).get("text") == text:
            return True


async def main() -> int:
    sender_url = GATEWAY + ctx["sender"]["token"]
    receiver_url = GATEWAY + ctx["receiver"]["token"]

    async with websockets.connect(sender_url) as sender:
        async with websockets.connect(receiver_url) as tab_one:
            tab_two = await websockets.connect(receiver_url)
            await asyncio.sleep(1)  # both sockets registered before the send

            both_text = ctx["text"] + " both"
            await sender.send(
                json.dumps(
                    {"event_type": "message", "receiver_id": CHANNEL, "text": both_text}
                )
            )
            got_one, got_two = await asyncio.gather(
                expect(tab_one, both_text), expect(tab_two, both_text)
            )
            report("first tab received the message", got_one)
            report("second tab received the message", got_two)

            # Closing one tab must leave the other one routed
            await tab_two.close()
            await asyncio.sleep(1)

            after_text = ctx["text"] + " after close"
            await sender.send(
                json.dumps(
                    {"event_type": "message", "receiver_id": CHANNEL, "text": after_text}
                )
            )
            report(
                "remaining tab still receives after the other closes",
                await expect(tab_one, after_text),
            )

    return 1 if FAILED else 0


sys.exit(asyncio.run(main()))
