import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from app.core.logger import logger

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining connections: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting WebSocket message: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

def broadcast_event_sync(event_type: str, data: Dict[str, Any]):
    """
    Helper to safely broadcast WebSocket events from synchronous code
    or background threads.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(manager.broadcast({"type": event_type, "data": data}))
        else:
            loop.run_until_complete(manager.broadcast({"type": event_type, "data": data}))
    except RuntimeError:
        # If no event loop in thread, create a new one
        new_loop = asyncio.new_event_loop()
        new_loop.run_until_complete(manager.broadcast({"type": event_type, "data": data}))
        new_loop.close()
    except Exception as e:
        logger.error(f"Failed to broadcast WS event sync: {e}")
