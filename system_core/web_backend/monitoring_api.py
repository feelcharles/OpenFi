"""
Monitoring and lifecycle API endpoints.

Provides REST APIs for:
- Health checks
- Prometheus metrics
- Metrics aggregation
- Manual cleanup trigger
- Readiness and liveness probes
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.database import get_db
from system_core.auth.middleware import get_current_user
from system_core.database.models import User
from system_core.monitoring import (
    get_health_checker,
    get_metrics_collector,
    MetricsAggregator,
    get_logger
)
from system_core.lifecycle import (
    CleanupJob,
    get_readiness_probe,
    get_liveness_probe
)

logger = get_logger(__name__)

router = APIRouter(tags=["monitoring"])

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Health check endpoint.
    
    Returns:
        - status: Overall health status (healthy/degraded/unhealthy)
        - uptime: System uptime in seconds
        - version: Application version
        - components: Status of each component
    
    Validates: Requirements 24.8, 35.5
    """
    try:
        health_checker = get_health_checker()
        
        # Get version from environment or config
        version = "1.0.0"  # TODO: Get from config or environment
        
        report = await health_checker.get_health_report(version=version)
        
        return report
        
    except Exception as e:
        logger.error(
            "health_check_error",
            exception_type=type(e).__name__,
            exception_message=str(e)
        )
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus exposition format.
    
    Validates: Requirements 25.1, 36.1
    """
    try:
        metrics_collector = get_metrics_collector()
        
        metrics_text = metrics_collector.get_metrics_text()
        content_type = metrics_collector.get_content_type()
        
        return Response(
            content=metrics_text,
            media_type=content_type
        )
        
    except Exception as e:
        logger.error(
            "metrics_endpoint_error",
            exception_type=type(e).__name__,
            exception_message=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to generate metrics")

@router.get("/api/metrics/summary")
async def get_metrics_summary(
    period: str = "24h",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Get aggregated metrics summary for a time period.
    
    Args:
        period: Time period (1h, 24h, 7d, 30d)
    
    Returns:
        Aggregated metrics including:
        - Signal metrics (total, high-value, rates)
        - Trade metrics (total, win rate, profit)
        - Notification metrics (total, success rate)
    
    Validates: Requirements 25.8, 36.7
    """
    try:
        if period not in ["1h", "24h", "7d", "30d"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid period. Must be one of: 1h, 24h, 7d, 30d"
            )
        
        aggregator = MetricsAggregator(db)
        summary = await aggregator.get_summary(period=period)
        
        return summary.to_dict()
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "metrics_summary_error",
            period=period,
            exception_type=type(e).__name__,
            exception_message=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to generate metrics summary")

@router.post("/api/admin/cleanup/run")
async def run_cleanup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """
    Manually trigger data cleanup job.
    
    Returns:
        - start_time: Cleanup start time
        - end_time: Cleanup end time
        - duration_seconds: Total duration
        - total_records_deleted: Total records deleted
        - total_records_archived: Total records archived
        - total_storage_freed_mb: Total storage freed in MB
        - results: Per-policy cleanup results
    
    Validates: Requirements 29.6, 29.7, 38.4
    """
    try:
        # Check if user has admin role
        if not hasattr(current_user, 'role') or current_user.role != 'admin':
            raise HTTPException(
                status_code=403,
                detail="Admin role required to run cleanup"
            )
        
        cleanup_job = CleanupJob(db)
        result = await cleanup_job.run_cleanup()
        
        logger.info(
            "manual_cleanup_completed",
            user_id=str(current_user.id),
            deleted=result["total_records_deleted"],
            archived=result["total_records_archived"]
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "cleanup_run_error",
            exception_type=type(e).__name__,
            exception_message=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to run cleanup job")

@router.get("/readiness")
async def readiness_probe() -> dict[str, Any]:
    """
    Readiness probe for Kubernetes/container orchestration.
    
    Indicates if application is ready to accept traffic.
    
    Returns:
        - ready: Boolean indicating readiness
        - timestamp: Check timestamp
        - checks: Individual check results
    
    Validates: Requirements 28.8, 37.4
    """
    try:
        probe = get_readiness_probe()
        result = await probe.check()
        
        # Return 503 if not ready
        if not result["ready"]:
            raise HTTPException(
                status_code=503,
                detail="Service not ready"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "readiness_probe_error",
            exception_type=type(e).__name__,
            exception_message=str(e)
        )
        raise HTTPException(status_code=500, detail="Readiness check failed")

@router.get("/liveness")
async def liveness_probe() -> dict[str, Any]:
    """
    Liveness probe for Kubernetes/container orchestration.
    
    Indicates if application is still running.
    
    Returns:
        - alive: Boolean indicating liveness
        - timestamp: Check timestamp
        - uptime_seconds: Application uptime
        - last_heartbeat: Last heartbeat timestamp
    
    Validates: Requirements 28.8, 37.4
    """
    try:
        probe = get_liveness_probe()
        result = await probe.check()
        
        # Return 503 if not alive
        if not result["alive"]:
            raise HTTPException(
                status_code=503,
                detail="Service not alive"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "liveness_probe_error",
            exception_type=type(e).__name__,
            exception_message=str(e)
        )
        raise HTTPException(status_code=500, detail="Liveness check failed")

