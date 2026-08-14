"""
WebSocket Manager for Real-time Application Signaling
"""

import json
from typing import Dict, List, Any
from fastapi import WebSocket
from app.core.logging import logger


class ConnectionManager:
    """Manages WebSocket connections and broadcasts events to target clients."""

    def __init__(self):
        # Maps agent_id string to a list of active WebSockets listening for updates
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, agent_id: str, websocket: WebSocket):
        """Accept a new WebSocket connection subscribed to a specific agent_id."""
        await websocket.accept()
        if agent_id not in self.active_connections:
            self.active_connections[agent_id] = []
        self.active_connections[agent_id].append(websocket)
        logger.info(f"WebSocket client connected for agent: {agent_id}")

    def disconnect(self, agent_id: str, websocket: WebSocket):
        """Remove a disconnected WebSocket."""
        if agent_id in self.active_connections:
            if websocket in self.active_connections[agent_id]:
                self.active_connections[agent_id].remove(websocket)
            if not self.active_connections[agent_id]:
                del self.active_connections[agent_id]
        logger.info(f"WebSocket client disconnected for agent: {agent_id}")

    async def broadcast_to_agent(self, agent_id: str, message: Dict[str, Any]):
        """Broadcast a JSON message to all WebSocket clients listening for an agent."""
        if agent_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[agent_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as exc:
                    logger.warning(f"Error sending WebSocket message: {exc}")
                    disconnected.append(connection)

            for conn in disconnected:
                self.disconnect(agent_id, conn)


manager = ConnectionManager()
