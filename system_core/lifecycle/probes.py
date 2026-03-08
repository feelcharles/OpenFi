"""
Health probes for Kubernetes/container orchestration.

Validates: Requirements 28.8
"""

from typing import Callable, Optional, Any
from datetime import datetime
import asyncio

from system_core.monitoring.logger import get_logger
from system_core.monitoring.health import ComponentStatus

logger = get_logger(__name__)

class ReadinessProbe:
    """
    Readiness probe indicates if application is ready to accept traffic.
    
    Validates: Requirements 28.8
    """
    
    def __init__(self):
        """Initialize readiness probe."""
        self.is_ready = False
        self.checks: dict[str, Callable] = {}
        self.last_check_time: Optional[datetime] = None
        self.last_status: Optional[bool] = None
    
    def register_check(self, name: str, check_func: Callable[[], bool]) -> None:
        """
        Register a readiness check.
        
        Args:
            name: Check name
            check_func: Function that returns True if ready
        """
        self.checks[name] = check_func
        logger.info("readiness_check_registered", check=name)
    
    async def check(self) -> dict[str, Any]:
        """
        Execute readiness checks.
        
        Returns:
            Dict containing readiness status and details
        """
        self.last_check_time = datetime.utcnow()
        
        results = {}
        all_ready = True
        
        for name, check_func in self.checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    is_ready = await check_func()
                else:
                    is_ready = check_func()
                
                results[name] = {
                    "ready": is_ready,
                    "message": "OK" if is_ready else "Not ready"
                }
                
                if not is_ready:
                    all_ready = False
                    
            except Exception as e:
                results[name] = {
                    "ready": False,
                    "message": f"Check failed: {str(e)}"
                }
                all_ready = False
                logger.error(
                    "readiness_check_error",
                    check=name,
                    exception_type=type(e).__name__,
                    exception_message=str(e)
                )
        
        self.is_ready = all_ready
        self.last_status = all_ready
        
        return {
            "ready": all_ready,
            "timestamp": self.last_check_time.isoformat(),
            "checks": results
        }
    
    def get_status(self) -> bool:
        """
        Get current readiness status.
        
        Returns:
            bool: True if ready to accept traffic
        """
        return self.is_ready

class LivenessProbe:
    """
    Liveness probe indicates if application is still running.
    
    Validates: Requirements 28.8
    """
    
    def __init__(self):
        """Initialize liveness probe."""
        self.is_alive = True
        self.start_time = datetime.utcnow()
        self.last_heartbeat: Optional[datetime] = None
        self.heartbeat_timeout = 60.0  # seconds
    
    def heartbeat(self) -> None:
        """
        Record heartbeat to indicate application is alive.
        """
        self.last_heartbeat = datetime.utcnow()
        self.is_alive = True
    
    async def check(self) -> dict[str, Any]:
        """
        Execute liveness check.
        
        Returns:
            Dict containing liveness status and details
        """
        now = datetime.utcnow()
        
        # Check if heartbeat is recent
        if self.last_heartbeat:
            time_since_heartbeat = (now - self.last_heartbeat).total_seconds()
            is_alive = time_since_heartbeat < self.heartbeat_timeout
        else:
            # No heartbeat yet, check if just started
            time_since_start = (now - self.start_time).total_seconds()
            is_alive = time_since_start < self.heartbeat_timeout
        
        self.is_alive = is_alive
        
        uptime = (now - self.start_time).total_seconds()
        
        return {
            "alive": is_alive,
            "timestamp": now.isoformat(),
            "uptime_seconds": uptime,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None
        }
    
    def get_status(self) -> bool:
        """
        Get current liveness status.
        
        Returns:
            bool: True if application is alive
        """
        return self.is_alive

# Global probe instances
_readiness_probe: Optional[ReadinessProbe] = None
_liveness_probe: Optional[LivenessProbe] = None

def get_readiness_probe() -> ReadinessProbe:
    """
    Get global readiness probe instance.
    
    Returns:
        ReadinessProbe: Global readiness probe
    """
    global _readiness_probe
    if _readiness_probe is None:
        _readiness_probe = ReadinessProbe()
    return _readiness_probe

def get_liveness_probe() -> LivenessProbe:
    """
    Get global liveness probe instance.
    
    Returns:
        LivenessProbe: Global liveness probe
    """
    global _liveness_probe
    if _liveness_probe is None:
        _liveness_probe = LivenessProbe()
    return _liveness_probe

def register_readiness_check(name: str, check_func: Callable[[], bool]) -> None:
    """
    Register a readiness check with the global probe.
    
    Args:
        name: Check name
        check_func: Check function
    """
    probe = get_readiness_probe()
    probe.register_check(name, check_func)
