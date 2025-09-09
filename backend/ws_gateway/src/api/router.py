import orjson
import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from libs.event.schema import Event
from src.auth.service import get_current_user_ws
from src.event.event_processor import event_processor
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
                event = Event(**orjson.loads(data), sender_id=current_user.id)
                logger.debug(f"Received event: {event}")
                await event_processor.enqueue_event(event)
            except Exception as e:
                logger.error(f"Error processing event: {e}")

    except WebSocketDisconnect:
        await websocket_manager.remove_client(current_user.id)
