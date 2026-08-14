import orjson
import structlog
from fastapi import APIRouter, Depends, Header, Request, status
from src.auth.utils import user_dependency
from src.core.config import settings
from src.utils.exceptions import UnauthorizedException
from src.voice.schemas import VoiceJoinResponse, VoiceParticipants
from src.voice.service import VoiceService, get_voice_service
from src.voice.webhooks import WebhookVerificationError, verify

logger = structlog.get_logger()

router = APIRouter(prefix="/channels", tags=["voice"])

# The webhook is not channel-scoped and is called by LiveKit, not a browser
webhook_router = APIRouter(prefix="/voice", tags=["voice"])


@router.post(
    "/{channel_id}/voice/join",
    response_model=VoiceJoinResponse,
    status_code=status.HTTP_200_OK,
)
async def join_voice_channel(
    channel_id: str,
    user: user_dependency,
    voice_service: VoiceService = Depends(get_voice_service),
):
    return await voice_service.join(user, channel_id)


@router.get(
    "/{channel_id}/voice/participants",
    response_model=VoiceParticipants,
    status_code=status.HTTP_200_OK,
)
async def get_voice_participants(
    channel_id: str,
    user: user_dependency,
    voice_service: VoiceService = Depends(get_voice_service),
):
    return await voice_service.participants(user, channel_id)


@webhook_router.post("/webhook", status_code=status.HTTP_200_OK)
async def livekit_webhook(
    request: Request,
    authorization: str | None = Header(default=None),
    voice_service: VoiceService = Depends(get_voice_service),
):
    """Presence, straight from the SFU.

    This is what makes the roster honest. A client that refreshes, crashes or
    is killed never sends a "leave", but LiveKit always notices the connection
    drop, so this is the only writer of the roster.

    **Never answer non-2xx once the signature checks out.** LiveKit retries a
    failed webhook, and its notifier is a single serialized queue per URL — one
    endlessly-failing event holds up every later one, so a bug here stops all
    presence rather than losing one event. Anything we cannot process is logged
    and acknowledged.
    """
    body = await request.body()
    try:
        verify(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
            authorization=authorization,
            body=body,
        )
    except WebhookVerificationError as e:
        # The only rejection. An unsigned call is not LiveKit, so refusing it
        # cannot stall LiveKit's queue.
        logger.warning("Rejected LiveKit webhook", error=str(e))
        raise UnauthorizedException("Invalid webhook signature")

    try:
        await _handle(payload=orjson.loads(body), voice_service=voice_service)
    except Exception:
        logger.exception("Failed to handle LiveKit webhook")
        return {"status": "error"}

    return {"status": "ok"}


# `event` is structlog's own name for the log message, so the LiveKit event
# type has to be bound under a different key or the call raises TypeError.
async def _handle(*, payload: dict, voice_service: VoiceService) -> None:
    livekit_event = payload.get("event")
    room = (payload.get("room") or {}).get("name")
    identity = (payload.get("participant") or {}).get("identity")

    if not room:
        logger.debug("Ignoring LiveKit webhook with no room", lk_event=livekit_event)
        return

    # `participant_connection_aborted` means they never finished connecting, so
    # they are not in the room either — same handling as a leave, and removing
    # someone who was never added is a no-op.
    left = livekit_event in ("participant_left", "participant_connection_aborted")

    if identity and (left or livekit_event == "participant_joined"):
        await voice_service.handle_participant_change(
            room=room, user_id=identity, joined=not left
        )
    elif livekit_event == "room_started":
        await voice_service.handle_room_started(room=room)
    elif livekit_event == "room_finished":
        await voice_service.handle_room_finished(room=room)
    else:
        logger.debug("Ignoring LiveKit webhook", lk_event=livekit_event, room=room)
