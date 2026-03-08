"""
Health check system for monitoring component status.

Validates: Requirements 24.8
"""

import time
from enum import Enum
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio

from .logger import get_logger

logger = get_logger(__name__)

class ComponentStatus(str, Enum):
    """Component health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class ComponentHealth:
    """Health information for a single component."""
    name: str
    status: ComponentStatus
    message: Optional[str] = None
    last_check: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "metadata": self.metadata
        }

class HealthChecker:
    """
    Health checker for monitoring system components.
    
    Validates: Requirements 24.8
    """
    
    def __init__(self):
        """Initialize health checker."""
        self.components: dict[str, Callable] = {}
        self.component_health: dict[str, ComponentHealth] = {}
        self.start_time = time.time()
    
    def register_component(
        self,
        name: str,
        check_func: Callable[[], bool]
    ) -> None:
        """
        Register a component health check function.
        
        Args:
            name: Component name
            check_func: Function that returns True if healthy, False otherwise
                       Can be sync or async
        """
        self.components[name] = check_func
        self.component_health[name] = ComponentHealth(
            name=name,
            status=ComponentStatus.UNKNOWN
        )
        logger.info("health_check_registered", component=name)
    
    async def check_component(self, name: str) -> ComponentHealth:
        """
        Check health of a specific component.
        
        Args:
            name: Component name
            
        Returns:
            ComponentHealth: Health status of component
        """
        if name not in self.components:
            return ComponentHealth(
                name=name,
                status=ComponentStatus.UNKNOWN,
                message=f"Component '{name}' not registered"
            )
        
        check_func = self.components[name]
        
        try:
            # Execute health check
            if asyncio.iscoroutinefunction(check_func):
                is_healthy = await check_func()
            else:
                is_healthy = check_func()
            
            status = ComponentStatus.HEALTHY if is_healthy else ComponentStatus.UNHEALTHY
            health = ComponentHealth(
                name=name,
                status=status,
                message="OK" if is_healthy else "Health check failed",
                last_check=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(
                "health_check_error",
                component=name,
                exception_type=type(e).__name__,
                exception_message=str(e)
            )
            health = ComponentHealth(
                name=name,
                status=ComponentStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                last_check=datetime.utcnow()
            )
        
        # Update cached health
        self.component_health[name] = health
        return health
    
    async def check_all(self) -> dict[str, ComponentHealth]:
        """
        Check health of all registered components.
        
        Returns:
            Dict mapping component names to health status
        """
        tasks = [
            self.check_component(name)
            for name in self.components.keys()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        health_map = {}
        for name, result in zip(self.components.keys(), results):
            if isinstance(result, Exception):
                health_map[name] = ComponentHealth(
                    name=name,
                    status=ComponentStatus.UNHEALTHY,
                    message=f"Check failed: {str(result)}",
                    last_check=datetime.utcnow()
                )
            else:
                health_map[name] = result
        
        return health_map
    
    def get_overall_status(self) -> ComponentStatus:
        """
        Get overall system health status.
        
        Returns:
            ComponentStatus: Overall status based on all components
            - HEALTHY: All components healthy
            - DEGRADED: Some components unhealthy but system functional
            - UNHEALTHY: Critical components unhealthy
        """
        if not self.component_health:
            return ComponentStatus.UNKNOWN
        
        statuses = [h.status for h in self.component_health.values()]
        
        if all(s == ComponentStatus.HEALTHY for s in statuses):
            return ComponentStatus.HEALTHY
        elif any(s == ComponentStatus.UNHEALTHY for s in statuses):
            # Check if critical components are unhealthy
            critical_components = ["database", "redis", "event_bus"]
            critical_unhealthy = any(
                self.component_health.get(name, ComponentHealth(name, ComponentStatus.UNKNOWN)).status == ComponentStatus.UNHEALTHY
                for name in critical_components
                if name in self.component_health
            )
            return ComponentStatus.UNHEALTHY if critical_unhealthy else ComponentStatus.DEGRADED
        else:
            return ComponentStatus.DEGRADED
    
    def get_uptime(self) -> float:
        """
        Get system uptime in seconds.
        
        Returns:
            float: Uptime in seconds
        """
        return time.time() - self.start_time
    
    async def get_health_report(self, version: str = "unknown") -> dict[str, Any]:
        """
        Get comprehensive health report.
        
        Args:
            version: Application version
            
        Returns:
            Dict containing health report with status, uptime, version, and component statuses
            
        Validates: Requirements 24.8
        """
        # Check all components
        component_health = await self.check_all()
        
        # Get overall status
        overall_status = self.get_overall_status()
        
        # Build report
        report = {
            "status": overall_status.value,
            "uptime": self.get_uptime(),
            "version": version,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                name: health.to_dict()
                for name, health in component_health.items()
            }
        }
        
        logger.info(
            "health_check_completed",
            status=overall_status.value,
            component_count=len(component_health)
        )
        
        return report

# Global health checker instance
_health_checker: Optional[HealthChecker] = None

def get_health_checker() -> HealthChecker:
    """
    Get global health checker instance.
    
    Returns:
        HealthChecker: Global health checker
    """
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker

def register_health_check(name: str, check_func: Callable[[], bool]) -> None:
    """
    Register a component health check.
    
    Args:
        name: Component name
        check_func: Health check function
    """
    checker = get_health_checker()
    checker.register_component(name, check_func)
