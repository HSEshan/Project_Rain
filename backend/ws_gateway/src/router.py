import json

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from src.auth import get_current_user_ws
from src.websocket_manager import websocket_manager

from libs.event.schema import Event

router = APIRouter(tags=["websocket", "gateway"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    print(f"Received token: {token}")
    current_user = await get_current_user_ws(token)
    await websocket_manager.add_client(
        client_id=current_user["id"], websocket=websocket
    )

    try:
        while True:
            data = await websocket.receive_text()
            event = Event(**json.loads(data))
            await websocket_manager.handle_event(event)

    except WebSocketDisconnect:
        await websocket_manager.remove_client(current_user["id"])
