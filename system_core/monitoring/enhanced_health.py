"""
Enhanced health check system with detailed component status and alert integration.

Validates: Requirements 36.7, 36.8
"""

from typing import Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from .health import HealthChecker, ComponentStatus, ComponentHealth
from .logger import get_logger
from ..database.client import get_session
from ..database.models import AlertLog

logger = get_logger(__name__)

@dataclass
class DetailedComponentStatus:
    """Detailed component status with metrics and recent alerts."""
    name: str
    status: ComponentStatus
    message: Optional[str] = None
    last_check: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    recent_alerts: list[dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "metadata": self.metadata,
            "metrics": self.metrics,
            "recent_alerts": self.recent_alerts
        }

class EnhancedHealthChecker:
    """
    Enhanced health checker with detailed component status and alert history.
    
    Validates: Requirements 36.7, 36.8
    """
    
    def __init__(self, base_checker: HealthChecker):
        """
        Initialize enhanced health checker.
        
        Args:
            base_checker: Base health checker instance
        """
        self.base_checker = base_checker
    
    async def get_recent_alerts(
        self,
        component: Optional[str] = None,
        hours: int = 24
    ) -> list[dict[str, Any]]:
        """
        Get recent alerts from database.
        
        Args:
            component: Filter by component name (None for all)
            hours: Number of hours to look back
            
        Returns:
            List of recent alerts
            
        Validates: Requirement 36.8
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            async with get_session() as session:
                from sqlalchemy import select
                
                query = select(AlertLog).where(
                    AlertLog.timestamp >= cutoff_time
                )
                
                if component:
                    query = query.where(AlertLog.component == component)
                
                query = query.order_by(AlertLog.timestamp.desc()).limit(10)
                
                result = await session.execute(query)
                alerts = result.scalars().all()
                
                return [
                    {
                        "id": str(alert.id),
                        "condition": alert.condition,
                        "severity": alert.severity,
                        "component": alert.component,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                        "metadata": alert.metadata,
                        "runbook_url": alert.runbook_url
                    }
                    for alert in alerts
                ]
        except Exception as e:
            logger.error(
                "failed_to_fetch_recent_alerts",
                component=component,
                error=str(e)
            )
            return []
    
    async def get_component_metrics(self, component: str) -> dict[str, Any]:
        """
        Get metrics for a specific component.
        
        Args:
            component: Component name
            
        Returns:
            Dict containing component metrics
        """
        metrics = {}
        
        try:
            # Get component-specific metrics based on component type
            if component == "database":
                metrics = await self._get_database_metrics()
            elif component == "redis":
                metrics = await self._get_redis_metrics()
            elif component == "event_bus":
                metrics = await self._get_event_bus_metrics()
            elif component == "fetch_engine":
                metrics = await self._get_fetch_engine_metrics()
            elif component == "ai_engine":
                metrics = await self._get_ai_engine_metrics()
            elif component == "execution_engine":
                metrics = await self._get_execution_engine_metrics()
            
        except Exception as e:
            logger.error(
                "failed_to_fetch_component_metrics",
                component=component,
                error=str(e)
            )
        
        return metrics
    
    async def _get_database_metrics(self) -> dict[str, Any]:
        """Get database metrics."""
        try:
            async with get_session() as session:
                from sqlalchemy import text
                
                # Get connection pool stats
                result = await session.execute(
                    text("SELECT count(*) FROM pg_stat_activity")
                )
                active_connections = result.scalar()
                
                return {
                    "active_connections": active_connections,
                    "status": "connected"
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _get_redis_metrics(self) -> dict[str, Any]:
        """Get Redis metrics."""
        try:
            from ..event_bus.event_bus import get_event_bus
            
            event_bus = get_event_bus()
            if hasattr(event_bus, 'redis_client'):
                info = await event_bus.redis_client.info()
                return {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory_human", "unknown"),
                    "uptime_seconds": info.get("uptime_in_seconds", 0)
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
        
        return {}
    
    async def _get_event_bus_metrics(self) -> dict[str, Any]:
        """Get event bus metrics."""
        try:
            from ..event_bus.event_bus import get_event_bus
            
            event_bus = get_event_bus()
            metrics = event_bus.get_metrics()
            
            return {
                "total_published": metrics.get("total_published", 0),
                "total_delivered": metrics.get("total_delivered", 0),
                "total_failed": metrics.get("total_failed", 0),
                "active_subscribers": metrics.get("active_subscribers", 0)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _get_fetch_engine_metrics(self) -> dict[str, Any]:
        """Get fetch engine metrics."""
        # This would query Prometheus or internal metrics
        return {
            "active_tasks": 0,
            "total_fetches_24h": 0,
            "success_rate": 0.0
        }
    
    async def _get_ai_engine_metrics(self) -> dict[str, Any]:
        """Get AI engine metrics."""
        # This would query Prometheus or internal metrics
        return {
            "total_llm_calls_24h": 0,
            "average_latency_seconds": 0.0,
            "success_rate": 0.0
        }
    
    async def _get_execution_engine_metrics(self) -> dict[str, Any]:
        """Get execution engine metrics."""
        # This would query Prometheus or internal metrics
        return {
            "total_trades_24h": 0,
            "active_positions": 0,
            "win_rate": 0.0
        }
    
    async def get_detailed_component_status(
        self,
        component: str
    ) -> DetailedComponentStatus:
        """
        Get detailed status for a specific component.
        
        Args:
            component: Component name
            
        Returns:
            DetailedComponentStatus: Detailed component status
            
        Validates: Requirement 36.7
        """
        # Get base health status
        base_health = await self.base_checker.check_component(component)
        
        # Get component metrics
        metrics = await self.get_component_metrics(component)
        
        # Get recent alerts for this component
        recent_alerts = await self.get_recent_alerts(component=component, hours=24)
        
        return DetailedComponentStatus(
            name=base_health.name,
            status=base_health.status,
            message=base_health.message,
            last_check=base_health.last_check,
            metadata=base_health.metadata,
            metrics=metrics,
            recent_alerts=recent_alerts
        )
    
    async def get_detailed_health_report(
        self,
        version: str = "unknown"
    ) -> dict[str, Any]:
        """
        Get comprehensive health report with detailed component status.
        
        Args:
            version: Application version
            
        Returns:
            Dict containing detailed health report
            
        Validates: Requirements 36.7, 36.8
        """
        # Get base health report
        base_report = await self.base_checker.get_health_report(version)
        
        # Enhance with detailed component status
        detailed_components = {}
        for component_name in self.base_checker.components.keys():
            detailed_status = await self.get_detailed_component_status(component_name)
            detailed_components[component_name] = detailed_status.to_dict()
        
        # Get system-wide recent alerts
        system_alerts = await self.get_recent_alerts(hours=24)
        
        # Build enhanced report
        report = {
            **base_report,
            "components": detailed_components,
            "recent_alerts": {
                "count": len(system_alerts),
                "alerts": system_alerts[:5]  # Top 5 most recent
            },
            "alert_summary": self._summarize_alerts(system_alerts)
        }
        
        logger.info(
            "detailed_health_check_completed",
            status=base_report["status"],
            component_count=len(detailed_components),
            alert_count=len(system_alerts)
        )
        
        return report
    
    def _summarize_alerts(self, alerts: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Summarize alerts by severity and component.
        
        Args:
            alerts: List of alerts
            
        Returns:
            Dict containing alert summary
        """
        summary = {
            "by_severity": {
                "critical": 0,
                "error": 0,
                "warning": 0,
                "info": 0
            },
            "by_component": {}
        }
        
        for alert in alerts:
            severity = alert.get("severity", "unknown")
            component = alert.get("component", "unknown")
            
            if severity in summary["by_severity"]:
                summary["by_severity"][severity] += 1
            
            if component not in summary["by_component"]:
                summary["by_component"][component] = 0
            summary["by_component"][component] += 1
        
        return summary

# Global enhanced health checker instance
_enhanced_health_checker: Optional[EnhancedHealthChecker] = None

def get_enhanced_health_checker() -> EnhancedHealthChecker:
    """
    Get global enhanced health checker instance.
    
    Returns:
        EnhancedHealthChecker: Global enhanced health checker
    """
    global _enhanced_health_checker
    if _enhanced_health_checker is None:
        from .health import get_health_checker
        base_checker = get_health_checker()
        _enhanced_health_checker = EnhancedHealthChecker(base_checker)
    return _enhanced_health_checker
