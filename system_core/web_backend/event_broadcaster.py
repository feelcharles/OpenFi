"""
Event Broadcaster for WebSocket real-time updates.

Subscribes to Event Bus topics and broadcasts events to WebSocket clients.
"""

import asyncio
from typing import Any, Optional

from system_core.web_backend.websocket_manager import ws_manager
from system_core.event_bus import EventBus
from system_core.config import get_logger

logger = get_logger(__name__)

class EventBroadcaster:
    """
    Broadcasts Event Bus events to WebSocket clients.
    
    Subscribes to:
    - ai.high_value_signal: High-value trading signals
    - trading.executed: Executed trades
    - system.health.*: System health events
    
    Requirements: 21.2
    """
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Initialize event broadcaster.
        
        Args:
            event_bus: Event bus instance (optional, can be set later)
        """
        self.event_bus = event_bus
        self._running = False
        self._tasks = []
        
        logger.info("event_broadcaster_initialized")
    
    def set_event_bus(self, event_bus: EventBus):
        """Set event bus instance."""
        self.event_bus = event_bus
        logger.info("event_bus_set")
    
    async def start(self):
        """
        Start broadcasting events.
        
        Subscribes to Event Bus topics and starts broadcasting.
        """
        if not self.event_bus:
            logger.error("event_broadcaster_start_failed", reason="event_bus_not_set")
            return
        
        if self._running:
            logger.warning("event_broadcaster_already_running")
            return
        
        self._running = True
        
        # Subscribe to topics
        await self.event_bus.subscribe("ai.high_value_signal", self._handle_high_value_signal)
        await self.event_bus.subscribe("trading.executed", self._handle_trade_executed)
        await self.event_bus.subscribe("system.health.*", self._handle_system_health)
        
        # Start WebSocket cleanup task
        await ws_manager.start_cleanup_task()
        
        logger.info("event_broadcaster_started")
    
    async def stop(self):
        """Stop broadcasting events."""
        if not self._running:
            return
        
        self._running = False
        
        # Unsubscribe from topics
        if self.event_bus:
            await self.event_bus.unsubscribe("ai.high_value_signal", self._handle_high_value_signal)
            await self.event_bus.unsubscribe("trading.executed", self._handle_trade_executed)
            await self.event_bus.unsubscribe("system.health.*", self._handle_system_health)
        
        # Stop WebSocket cleanup task
        await ws_manager.stop_cleanup_task()
        
        logger.info("event_broadcaster_stopped")
    
    async def _handle_high_value_signal(self, event: dict[str, Any]):
        """
        Handle high-value signal events.
        
        Args:
            event: Event data from Event Bus
        """
        try:
            payload = event.get("payload", {})
            
            message = {
                "type": "signal",
                "data": {
                    "signal_id": payload.get("signal_id"),
                    "source": payload.get("source"),
                    "relevance_score": payload.get("relevance_score"),
                    "potential_impact": payload.get("potential_impact"),
                    "summary": payload.get("summary"),
                    "suggested_actions": payload.get("suggested_actions"),
                    "related_symbols": payload.get("related_symbols"),
                    "confidence": payload.get("confidence")
                },
                "timestamp": event.get("timestamp")
            }
            
            await ws_manager.broadcast(message)
            
            logger.info(
                "signal_broadcasted",
                signal_id=payload.get("signal_id"),
                recipients=ws_manager.get_connection_count()
            )
            
        except Exception as e:
            logger.error("signal_broadcast_error", error=str(e), event=event)
    
    async def _handle_trade_executed(self, event: dict[str, Any]):
        """
        Handle trade execution events.
        
        Args:
            event: Event data from Event Bus
        """
        try:
            payload = event.get("payload", {})
            
            message = {
                "type": "trade",
                "data": {
                    "trade_id": payload.get("trade_id"),
                    "order_id": payload.get("order_id"),
                    "symbol": payload.get("symbol"),
                    "direction": payload.get("direction"),
                    "volume": payload.get("volume"),
                    "entry_price": payload.get("entry_price"),
                    "stop_loss": payload.get("stop_loss"),
                    "take_profit": payload.get("take_profit"),
                    "status": payload.get("status")
                },
                "timestamp": event.get("timestamp")
            }
            
            await ws_manager.broadcast(message)
            
            logger.info(
                "trade_broadcasted",
                trade_id=payload.get("trade_id"),
                recipients=ws_manager.get_connection_count()
            )
            
        except Exception as e:
            logger.error("trade_broadcast_error", error=str(e), event=event)
    
    async def _handle_system_health(self, event: dict[str, Any]):
        """
        Handle system health events.
        
        Args:
            event: Event data from Event Bus
        """
        try:
            payload = event.get("payload", {})
            
            message = {
                "type": "system_event",
                "data": {
                    "component": payload.get("component"),
                    "status": payload.get("status"),
                    "message": payload.get("message"),
                    "details": payload.get("details")
                },
                "timestamp": event.get("timestamp")
            }
            
            await ws_manager.broadcast(message)
            
            logger.info(
                "system_event_broadcasted",
                component=payload.get("component"),
                status=payload.get("status"),
                recipients=ws_manager.get_connection_count()
            )
            
        except Exception as e:
            logger.error("system_event_broadcast_error", error=str(e), event=event)
    
    def is_running(self) -> bool:
        """Check if broadcaster is running."""
        return self._running

# Global event broadcaster instance
event_broadcaster = EventBroadcaster()
