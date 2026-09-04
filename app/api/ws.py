from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.ws_manager import manager
from app.core.logger import logger

router = APIRouter(prefix="/ws", tags=["WebSocket"])

@router.websocket("")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive with ping/pong
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
