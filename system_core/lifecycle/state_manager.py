"""
State persistence and recovery management.

Validates: Requirements 28.6, 28.7
"""

import json
import asyncio
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

from system_core.monitoring.logger import get_logger

logger = get_logger(__name__)

class StateManager:
    """
    Manages application state persistence and recovery.
    
    Validates: Requirements 28.6, 28.7
    """
    
    def __init__(self, state_file: str = "state/application_state.json"):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to state file
        """
        self.state_file = Path(state_file)
        self.state: dict[str, Any] = {}
        
        # Ensure state directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
    
    async def save_state(self, component: str, state_data: dict[str, Any]) -> None:
        """
        Save component state to disk.
        
        Args:
            component: Component name
            state_data: State data to save
            
        Validates: Requirements 28.6
        """
        try:
            # Update in-memory state
            self.state[component] = {
                "data": state_data,
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0"
            }
            
            # Write to disk
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._write_state_file
            )
            
            logger.info(
                "state_saved",
                component=component,
                keys=list(state_data.keys())
            )
            
        except Exception as e:
            logger.error(
                "state_save_error",
                component=component,
                exception_type=type(e).__name__,
                exception_message=str(e)
            )
    
    def _write_state_file(self) -> None:
        """Write state to file (sync operation)."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    async def load_state(self, component: str) -> Optional[dict[str, Any]]:
        """
        Load component state from disk.
        
        Args:
            component: Component name
            
        Returns:
            Dict containing state data, or None if not found
            
        Validates: Requirements 28.7
        """
        try:
            # Load from disk if not in memory
            if not self.state and self.state_file.exists():
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._read_state_file
                )
            
            # Get component state
            component_state = self.state.get(component)
            
            if component_state:
                logger.info(
                    "state_loaded",
                    component=component,
                    timestamp=component_state.get("timestamp"),
                    keys=list(component_state.get("data", {}).keys())
                )
                return component_state.get("data")
            else:
                logger.info(
                    "state_not_found",
                    component=component
                )
                return None
                
        except Exception as e:
            logger.error(
                "state_load_error",
                component=component,
                exception_type=type(e).__name__,
                exception_message=str(e)
            )
            return None
    
    def _read_state_file(self) -> None:
        """Read state from file (sync operation)."""
        with open(self.state_file, 'r') as f:
            self.state = json.load(f)
    
    async def save_fetch_engine_state(self, active_tasks: dict[str, Any]) -> None:
        """
        Save fetch engine state.
        
        Args:
            active_tasks: Dict of active fetch tasks
        """
        await self.save_state("fetch_engine", {
            "active_tasks": active_tasks
        })
    
    async def load_fetch_engine_state(self) -> Optional[dict[str, Any]]:
        """
        Load fetch engine state.
        
        Returns:
            Dict containing active tasks, or None
        """
        state = await self.load_state("fetch_engine")
        return state.get("active_tasks") if state else None
    
    async def save_pending_signals(self, signals: list) -> None:
        """
        Save pending signals.
        
        Args:
            signals: List of pending signals
        """
        await self.save_state("pending_signals", {
            "signals": signals,
            "count": len(signals)
        })
    
    async def load_pending_signals(self) -> Optional[list]:
        """
        Load pending signals.
        
        Returns:
            List of pending signals, or None
        """
        state = await self.load_state("pending_signals")
        return state.get("signals") if state else None
    
    async def save_circuit_breaker_state(self, circuit_breakers: dict[str, Any]) -> None:
        """
        Save circuit breaker states.
        
        Args:
            circuit_breakers: Dict of circuit breaker states by EA profile ID
        """
        await self.save_state("circuit_breakers", circuit_breakers)
    
    async def load_circuit_breaker_state(self) -> Optional[dict[str, Any]]:
        """
        Load circuit breaker states.
        
        Returns:
            Dict of circuit breaker states, or None
        """
        return await self.load_state("circuit_breakers")
    
    async def clear_state(self, component: Optional[str] = None) -> None:
        """
        Clear state for component or all components.
        
        Args:
            component: Component name, or None to clear all
        """
        if component:
            if component in self.state:
                del self.state[component]
                logger.info("state_cleared", component=component)
        else:
            self.state = {}
            logger.info("all_state_cleared")
        
        # Write to disk
        await asyncio.get_event_loop().run_in_executor(
            None,
            self._write_state_file
        )

# Global state manager instance
_state_manager: Optional[StateManager] = None

def get_state_manager() -> StateManager:
    """
    Get global state manager instance.
    
    Returns:
        StateManager: Global state manager
    """
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager
