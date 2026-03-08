"""
WebSocket API endpoints for real-time updates.

Provides WebSocket endpoint for real-time event broadcasting.
"""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.web_backend.websocket_manager import ws_manager
from system_core.database import get_db
from system_core.config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])

@router.websocket("/ws/notifications")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = Query(default=None)
):
    """
    WebSocket endpoint for real-time notifications.
    
    Clients can connect to receive real-time updates about:
    - High-value signals (ai.high_value_signal)
    - Executed trades (trading.executed)
    - System health events (system.health.*)
    
    Message format:
    {
        "type": "signal" | "trade" | "system_event",
        "timestamp": "ISO 8601 timestamp",
        "data": { ... event-specific data ... }
    }
    
    Requirements: 21.2
    """
    client_id = await ws_manager.connect(websocket, client_id)
    
    try:
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle client message
                await ws_manager.handle_client_message(client_id, message)
                
            except json.JSONDecodeError as e:
                logger.warning("websocket_invalid_json", client_id=client_id, error=str(e))
                await ws_manager.send_to_client(client_id, {
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            except WebSocketDisconnect:
                logger.info("websocket_client_disconnected", client_id=client_id)
                break
            except Exception as e:
                logger.error("websocket_message_error", client_id=client_id, error=str(e))
                break
    
    finally:
        await ws_manager.disconnect(client_id)

@router.get("/ws/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.
    
    Returns:
        Connection statistics including active connections and message counts
    """
    stats = ws_manager.get_connection_stats()
    logger.debug("websocket_stats_retrieved", stats=stats)
    return stats
