from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from .contracts import WebSocketEnvelope


class WebSocketSessionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id].append(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        if session_id not in self._connections:
            return
        self._connections[session_id] = [connection for connection in self._connections[session_id] if connection is not websocket]
        if not self._connections[session_id]:
            self._connections.pop(session_id, None)

    async def broadcast(self, session_id: str, message: WebSocketEnvelope) -> None:
        stale_connections: list[WebSocket] = []
        for connection in self._connections.get(session_id, []):
            try:
                await connection.send_json(message.model_dump(mode="json"))
            except WebSocketDisconnect:
                stale_connections.append(connection)
            except RuntimeError:
                stale_connections.append(connection)
        for connection in stale_connections:
            self.disconnect(session_id, connection)


ws_manager = WebSocketSessionManager()
