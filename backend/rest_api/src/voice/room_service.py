"""Telling LiveKit that someone has lost the right to be in a room.

The client leaves by itself when a channel stops being its own, but that is a
courtesy and not a control: a modified client would simply stay. Removal has to be
something the server does.

Best effort, like publishing, and for the same reason: by the time this runs the
transaction has committed, so an SFU outage must not turn a removal that happened
into a 500. It is logged, and the client's own departure still covers everyone who
has not gone out of their way to avoid it.

A removed participant's join token stays valid until it expires (`TOKEN_TTL`).
LiveKit does not revoke tokens, so a hostile client could connect again with the
one it holds. It cannot get a new one: `join` checks membership.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import structlog
from jose import jwt
from src.core.config import settings

logger = structlog.get_logger()

REQUEST_TIMEOUT_SECONDS = 3


def _admin_token(room: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        claims={
            "iss": settings.LIVEKIT_API_KEY,
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=1)).timestamp()),
            # LiveKit's claim keys, see tokens.py. Scoped to the one room.
            "video": {"room": room, "roomAdmin": True, "roomCreate": True},
        },
        key=settings.LIVEKIT_API_SECRET,
        algorithm="HS256",
    )


async def _call(
    client: httpx.AsyncClient, method: str, room: str, body: dict
) -> None:
    url = f"{settings.LIVEKIT_INTERNAL_URL}/twirp/livekit.RoomService/{method}"
    try:
        response = await client.post(
            url,
            json=body,
            headers={"Authorization": f"Bearer {_admin_token(room)}"},
        )
        # 404 is the room or participant having gone already, which is the outcome
        if response.status_code >= 400 and response.status_code != 404:
            logger.warning(
                "LiveKit refused a room change",
                method=method,
                status=response.status_code,
            )
    except httpx.HTTPError:
        logger.exception("Could not reach LiveKit", method=method)


async def _call_all(method: str, rooms: list[str], body_for) -> None:
    """Every room at once, so an SFU that is down costs one timeout and not one
    per room. Callers run this last, after publishing, so it delays nobody's news."""
    if not settings.LIVEKIT_API_SECRET or not rooms:
        return
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        await asyncio.gather(
            *(_call(client, method, room, body_for(room)) for room in rooms)
        )


async def remove_from_rooms(rooms: list[str], identity: str) -> None:
    """Disconnect someone from whichever of these rooms they are in.

    Asks about every room rather than reading the roster first. The roster fills
    from a webhook that only fires once a participant is fully active, so someone
    mid-connection, or a client that never finishes connecting, is not on it. A
    room they are not in is a 404, and a guild has few voice channels.
    """
    await _call_all(
        "RemoveParticipant", rooms, lambda room: {"room": room, "identity": identity}
    )


async def close_rooms(rooms: list[str]) -> None:
    """End these rooms for everyone in them, because their channels are gone."""
    await _call_all("DeleteRoom", rooms, lambda room: {"room": room})
