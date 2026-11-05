import orjson
import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from libs.rate_limit import hit
from src.auth.service import get_current_user_ws
from src.core.config import settings
from src.event.event_queue import event_queue
from src.message.ingest import MESSAGE_RATE, build_client_event, rate_limited_frame
from src.websocket.manager import websocket_manager

logger = structlog.get_logger()

router = APIRouter(tags=["websocket", "gateway"])


@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    current_user = await get_current_user_ws(token)
    await websocket_manager.add_client(current_user=current_user, websocket=websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                # Before parsing, so that junk is counted too: anything a client
                # sends is meant to be a message. Keyed on the account, not the
                # socket, or a second tab would double the limit.
                if settings.RATE_LIMIT_ENABLED:
                    decision = await hit(
                        websocket_manager.redis_manager.redis,
                        MESSAGE_RATE,
                        current_user.id,
                    )
                    if not decision.allowed:
                        await websocket.send_json(
                            rate_limited_frame(current_user.id, decision.retry_after)
                        )
                        continue
                event = build_client_event(orjson.loads(data), current_user.id)
                if event is None:
                    continue
                logger.debug(f"Received event: {event}")
                await event_queue.enqueue_event(event)
            except Exception as e:
                logger.error(f"Error processing event: {e}")

    except WebSocketDisconnect:
        await websocket_manager.remove_client(current_user.id, websocket)
