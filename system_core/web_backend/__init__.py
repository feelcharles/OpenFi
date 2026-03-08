"""
Web Backend module for OpenFi Lite.

Provides REST APIs and WebSocket endpoints for web dashboard.
"""

from system_core.web_backend.api import router as web_api_router
from system_core.web_backend.websocket_api import router as websocket_router
from system_core.web_backend.websocket_manager import WebSocketManager, ws_manager
from system_core.web_backend.event_broadcaster import EventBroadcaster, event_broadcaster
from system_core.web_backend.middleware import RateLimitMiddleware, setup_cors
from system_core.web_backend.app import create_app, app

__all__ = [
    "web_api_router",
    "websocket_router",
    "WebSocketManager",
    "ws_manager",
    "EventBroadcaster",
    "event_broadcaster",
    "RateLimitMiddleware",
    "setup_cors",
    "create_app",
    "app"
]
