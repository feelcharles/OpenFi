"""
Graceful shutdown management.

Validates: Requirements 28.1, 28.2, 28.3, 28.4, 28.5
"""

import signal
import asyncio
import sys
from typing import Callable, Optional, Any
from dataclasses import dataclass

from system_core.monitoring.logger import get_logger

logger = get_logger(__name__)

@dataclass
class ShutdownHandler:
    """Shutdown handler registration."""
    name: str
    handler: Callable
    priority: int = 0  # Higher priority runs first
    timeout: float = 30.0

class ShutdownManager:
    """
    Manages graceful shutdown of the application.
    
    Validates: Requirements 28.1, 28.2, 28.3, 28.4, 28.5
    """
    
    def __init__(self):
        """Initialize shutdown manager."""
        self.handlers: list[ShutdownHandler] = []
        self.is_shutting_down = False
        self.shutdown_event = asyncio.Event()
    
    def register_handler(
        self,
        name: str,
        handler: Callable,
        priority: int = 0,
        timeout: float = 30.0
    ) -> None:
        """
        Register a shutdown handler.
        
        Args:
            name: Handler name for logging
            handler: Async function to call during shutdown
            priority: Priority (higher runs first)
            timeout: Maximum time to wait for handler (seconds)
        """
        self.handlers.append(
            ShutdownHandler(
                name=name,
                handler=handler,
                priority=priority,
                timeout=timeout
            )
        )
        # Sort by priority (descending)
        self.handlers.sort(key=lambda h: h.priority, reverse=True)
        
        logger.info(
            "shutdown_handler_registered",
            handler=name,
            priority=priority,
            timeout=timeout
        )
    
    def setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for SIGTERM and SIGINT.
        
        Validates: Requirements 28.1
        """
        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            signal_name = signal.Signals(signum).name
            logger.info(
                "shutdown_signal_received",
                signal=signal_name
            )
            
            # Trigger shutdown
            asyncio.create_task(self.shutdown())
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        logger.info("shutdown_signal_handlers_registered")
    
    async def shutdown(self) -> None:
        """
        Execute graceful shutdown sequence.
        
        Validates: Requirements 28.2, 28.3, 28.4, 28.5
        """
        if self.is_shutting_down:
            logger.warning("shutdown_already_in_progress")
            return
        
        self.is_shutting_down = True
        logger.info("shutdown_initiated", handler_count=len(self.handlers))
        
        # Stop accepting new requests immediately (Requirements 28.2)
        self.shutdown_event.set()
        
        # Execute shutdown handlers in priority order
        for handler_info in self.handlers:
            try:
                logger.info(
                    "shutdown_handler_executing",
                    handler=handler_info.name,
                    priority=handler_info.priority,
                    timeout=handler_info.timeout
                )
                
                # Execute handler with timeout
                if asyncio.iscoroutinefunction(handler_info.handler):
                    await asyncio.wait_for(
                        handler_info.handler(),
                        timeout=handler_info.timeout
                    )
                else:
                    # Run sync handler in executor
                    loop = asyncio.get_event_loop()
                    await asyncio.wait_for(
                        loop.run_in_executor(None, handler_info.handler),
                        timeout=handler_info.timeout
                    )
                
                logger.info(
                    "shutdown_handler_completed",
                    handler=handler_info.name
                )
                
            except asyncio.TimeoutError:
                logger.error(
                    "shutdown_handler_timeout",
                    handler=handler_info.name,
                    timeout=handler_info.timeout
                )
            except Exception as e:
                logger.error(
                    "shutdown_handler_error",
                    handler=handler_info.name,
                    exception_type=type(e).__name__,
                    exception_message=str(e),
                    exc_info=True
                )
        
        logger.info("shutdown_completed")
    
    def is_shutdown_requested(self) -> bool:
        """
        Check if shutdown has been requested.
        
        Returns:
            bool: True if shutdown is in progress
        """
        return self.is_shutting_down
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self.shutdown_event.wait()

# Global shutdown manager instance
_shutdown_manager: Optional[ShutdownManager] = None

def get_shutdown_manager() -> ShutdownManager:
    """
    Get global shutdown manager instance.
    
    Returns:
        ShutdownManager: Global shutdown manager
    """
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = ShutdownManager()
    return _shutdown_manager

def register_shutdown_handler(
    name: str,
    handler: Callable,
    priority: int = 0,
    timeout: float = 30.0
) -> None:
    """
    Register a shutdown handler with the global manager.
    
    Args:
        name: Handler name
        handler: Shutdown handler function
        priority: Priority (higher runs first)
        timeout: Maximum time to wait (seconds)
    """
    manager = get_shutdown_manager()
    manager.register_handler(name, handler, priority, timeout)

async def shutdown_event_bus(event_bus) -> None:
    """
    Shutdown handler for event bus.
    
    Waits up to 30 seconds for in-flight messages to complete.
    
    Args:
        event_bus: EventBus instance
        
    Validates: Requirements 28.3
    """
    logger.info("event_bus_shutdown_started")
    
    try:
        # Wait for in-flight messages (up to 30 seconds)
        await asyncio.wait_for(
            event_bus.graceful_shutdown(),
            timeout=30.0
        )
        logger.info("event_bus_shutdown_completed")
    except asyncio.TimeoutError:
        logger.warning("event_bus_shutdown_timeout")
    except Exception as e:
        logger.error(
            "event_bus_shutdown_error",
            exception_type=type(e).__name__,
            exception_message=str(e)
        )

async def shutdown_database(db_session) -> None:
    """
    Shutdown handler for database connections.
    
    Closes connections and flushes pending writes.
    
    Args:
        db_session: Database session
        
    Validates: Requirements 28.4
    """
    logger.info("database_shutdown_started")
    
    try:
        # Flush pending writes
        await asyncio.get_event_loop().run_in_executor(
            None,
            db_session.commit
        )
        
        # Close connections
        await asyncio.get_event_loop().run_in_executor(
            None,
            db_session.close
        )
        
        logger.info("database_shutdown_completed")
    except Exception as e:
        logger.error(
            "database_shutdown_error",
            exception_type=type(e).__name__,
            exception_message=str(e)
        )

async def shutdown_external_connections(connections: list[Any]) -> None:
    """
    Shutdown handler for external API connections.
    
    Closes connections to LLM providers, brokers, push channels.
    
    Args:
        connections: List of connection objects with close() method
        
    Validates: Requirements 28.5
    """
    logger.info(
        "external_connections_shutdown_started",
        connection_count=len(connections)
    )
    
    for conn in connections:
        try:
            if hasattr(conn, 'close'):
                if asyncio.iscoroutinefunction(conn.close):
                    await conn.close()
                else:
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        conn.close
                    )
            logger.info(
                "external_connection_closed",
                connection_type=type(conn).__name__
            )
        except Exception as e:
            logger.error(
                "external_connection_close_error",
                connection_type=type(conn).__name__,
                exception_type=type(e).__name__,
                exception_message=str(e)
            )
    
    logger.info("external_connections_shutdown_completed")
