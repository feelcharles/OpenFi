"""
WebSocket Manager for real-time updates.

Manages WebSocket connections and broadcasts events to connected clients.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4
from collections import defaultdict

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from system_core.config import get_logger

logger = get_logger(__name__)

class WebSocketManager:
    """
    Manages WebSocket connections and real-time event broadcasting.
    
    Features:
    - Connection management (connect, disconnect)
    - Real-time event broadcasting
    - Rate limiting (1000 messages per minute per connection)
    - Automatic cleanup of stale connections
    
    Requirements: 21.2, 21.6
    """
    
    def __init__(self):
        """Initialize WebSocket manager."""
        self.active_connections: dict[str, WebSocket] = {}
        self.connection_metadata: dict[str, dict[str, Any]] = {}
        self.message_counts: dict[str, list] = defaultdict(list)
        self.rate_limit = 1000  # messages per minute
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info("websocket_manager_initialized")
    
    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            client_id: Optional client identifier (generated if not provided)
        
        Returns:
            Client ID for the connection
        
        Requirements: 21.2
        """
        await websocket.accept()
        
        if client_id is None:
            client_id = str(uuid4())
        
        self.active_connections[client_id] = websocket
        self.connection_metadata[client_id] = {
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "messages_sent": 0,
            "messages_received": 0
        }
        
        logger.info(
            "websocket_connected",
            client_id=client_id,
            total_connections=len(self.active_connections)
        )
        
        # Send welcome message
        await self.send_to_client(client_id, {
            "type": "connection",
            "message": "Connected to OpenFi Lite WebSocket",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return client_id
    
    async def disconnect(self, client_id: str):
        """
        Disconnect and cleanup a WebSocket connection.
        
        Args:
            client_id: Client identifier
        
        Requirements: 21.2
        """
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            
            # Close connection if still open
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.close()
                except Exception as e:
                    logger.warning("websocket_close_error", client_id=client_id, error=str(e))
            
            # Remove from tracking
            del self.active_connections[client_id]
            
            if client_id in self.connection_metadata:
                metadata = self.connection_metadata[client_id]
                duration = (datetime.utcnow() - metadata["connected_at"]).total_seconds()
                
                logger.info(
                    "websocket_disconnected",
                    client_id=client_id,
                    duration_seconds=duration,
                    messages_sent=metadata["messages_sent"],
                    messages_received=metadata["messages_received"],
                    total_connections=len(self.active_connections)
                )
                
                del self.connection_metadata[client_id]
            
            # Cleanup message counts
            if client_id in self.message_counts:
                del self.message_counts[client_id]
    
    async def send_to_client(self, client_id: str, message: dict[str, Any]) -> bool:
        """
        Send message to a specific client.
        
        Args:
            client_id: Client identifier
            message: Message to send
        
        Returns:
            True if sent successfully, False otherwise
        
        Requirements: 21.2
        """
        if client_id not in self.active_connections:
            logger.warning("websocket_client_not_found", client_id=client_id)
            return False
        
        websocket = self.active_connections[client_id]
        
        # Pre-increment for rate limit check
        now = datetime.utcnow()
        self.message_counts[client_id].append(now)
        
        # Check rate limit
        if not self._check_rate_limit(client_id):
            # Rollback the pre-increment
            self.message_counts[client_id].pop()
            logger.warning("websocket_rate_limit_exceeded", client_id=client_id)
            return False
        
        try:
            # Add timestamp if not present
            if "timestamp" not in message:
                message["timestamp"] = now.isoformat()
            
            await websocket.send_json(message)
            
            # Update metadata
            if client_id in self.connection_metadata:
                self.connection_metadata[client_id]["messages_sent"] += 1
                self.connection_metadata[client_id]["last_activity"] = now
            
            return True
            
        except WebSocketDisconnect:
            logger.info("websocket_disconnected_during_send", client_id=client_id)
            # Rollback the count on failure
            if self.message_counts[client_id]:
                self.message_counts[client_id].pop()
            await self.disconnect(client_id)
            return False
        except Exception as e:
            logger.error("websocket_send_error", client_id=client_id, error=str(e))
            # Rollback the count on failure
            if self.message_counts[client_id]:
                self.message_counts[client_id].pop()
            await self.disconnect(client_id)
            return False
    
    async def broadcast(self, message: dict[str, Any], exclude: Optional[set[str]] = None):
        """
        Broadcast message to all connected clients.
        
        Args:
            message: Message to broadcast
            exclude: Set of client IDs to exclude from broadcast
        
        Requirements: 21.2
        """
        if exclude is None:
            exclude = set()
        
        # Add timestamp
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()
        
        disconnected_clients = []
        success_count = 0
        
        for client_id in list(self.active_connections.keys()):
            if client_id in exclude:
                continue
            
            success = await self.send_to_client(client_id, message)
            if success:
                success_count += 1
            else:
                disconnected_clients.append(client_id)
        
        # Cleanup disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect(client_id)
        
        logger.debug(
            "websocket_broadcast",
            message_type=message.get("type"),
            recipients=success_count,
            excluded=len(exclude),
            failed=len(disconnected_clients)
        )
    
    def _check_rate_limit(self, client_id: str) -> bool:
        """
        Check if client has exceeded rate limit.
        
        Args:
            client_id: Client identifier
        
        Returns:
            True if within limit, False if exceeded
        
        Requirements: 21.6
        """
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old messages
        self.message_counts[client_id] = [
            msg_time for msg_time in self.message_counts[client_id]
            if msg_time > minute_ago
        ]
        
        # Check limit
        return len(self.message_counts[client_id]) < self.rate_limit
    
    async def handle_client_message(self, client_id: str, message: dict[str, Any]):
        """
        Handle incoming message from client.
        
        Args:
            client_id: Client identifier
            message: Received message
        """
        if client_id in self.connection_metadata:
            self.connection_metadata[client_id]["messages_received"] += 1
            self.connection_metadata[client_id]["last_activity"] = datetime.utcnow()
        
        logger.debug("websocket_message_received", client_id=client_id, message_type=message.get("type"))
        
        # Handle ping/pong for keepalive
        if message.get("type") == "ping":
            await self.send_to_client(client_id, {"type": "pong", "timestamp": datetime.utcnow().isoformat()})
    
    async def cleanup_stale_connections(self):
        """
        Periodically cleanup stale connections.
        
        Disconnects clients that haven't sent any activity in 5 minutes.
        """
        while True:
            await asyncio.sleep(60)  # Check every minute
            
            now = datetime.utcnow()
            stale_timeout = timedelta(minutes=5)
            stale_clients = []
            
            for client_id, metadata in self.connection_metadata.items():
                if now - metadata["last_activity"] > stale_timeout:
                    stale_clients.append(client_id)
            
            for client_id in stale_clients:
                logger.info("websocket_stale_connection_cleanup", client_id=client_id)
                await self.disconnect(client_id)
            
            if stale_clients:
                logger.info("websocket_cleanup_completed", removed=len(stale_clients))
    
    def get_connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.active_connections)
    
    def get_connection_stats(self) -> dict[str, Any]:
        """Get connection statistics."""
        total_messages_sent = sum(
            meta["messages_sent"] for meta in self.connection_metadata.values()
        )
        total_messages_received = sum(
            meta["messages_received"] for meta in self.connection_metadata.values()
        )
        
        return {
            "active_connections": len(self.active_connections),
            "total_messages_sent": total_messages_sent,
            "total_messages_received": total_messages_received,
            "rate_limit": self.rate_limit
        }
    
    async def start_cleanup_task(self):
        """Start background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self.cleanup_stale_connections())
            logger.info("websocket_cleanup_task_started")
    
    async def stop_cleanup_task(self):
        """Stop background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("websocket_cleanup_task_stopped")

# Global WebSocket manager instance
ws_manager = WebSocketManager()
