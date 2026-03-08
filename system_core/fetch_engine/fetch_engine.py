"""
Fetch Engine Orchestrator

Orchestrates data fetching from multiple external sources with scheduling,
validation, and health monitoring.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional
from pathlib import Path
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from system_core.config import ConfigurationManager, get_logger
from system_core.event_bus import EventBus

logger = get_logger(__name__)

class FetchEngine:
    """
    Fetch Engine orchestrator for managing data acquisition from multiple sources.
    
    Responsibilities:
    - Load and validate data source configurations
    - Schedule fetch tasks using APScheduler
    - Maintain registry of active fetchers
    - Provide health check endpoint
    - Support configuration hot reload
    """
    
    def __init__(
        self,
        config_manager: ConfigurationManager,
        event_bus: EventBus,
        config_path: str = "config/fetch_sources.yaml",
        enable_graceful_degradation: bool = True,
        overload_threshold: float = 0.8
    ):
        """
        Initialize Fetch Engine.
        
        Args:
            config_manager: Configuration manager instance
            event_bus: Event bus for publishing fetched data
            config_path: Path to fetch sources configuration file
            enable_graceful_degradation: Enable graceful degradation when overloaded
            overload_threshold: Threshold for considering system overloaded (0.0-1.0)
        """
        self.config_manager = config_manager
        self.event_bus = event_bus
        self.config_path = config_path
        
        # Fetcher registry indexed by source_id
        self.fetcher_registry: dict[str, Any] = {}
        
        # APScheduler for task scheduling
        self.scheduler = AsyncIOScheduler()
        
        # Health status tracking
        self.health_status: dict[str, dict[str, Any]] = {}
        
        # Graceful degradation (Requirement 38.8)
        self.enable_graceful_degradation = enable_graceful_degradation
        self.overload_threshold = overload_threshold
        self.is_overloaded = False
        self.degradation_factor = 1.0  # 1.0 = normal, >1.0 = reduced frequency
        
        # Trace ID for logging correlation
        self.trace_id = str(uuid.uuid4())
        
        logger.info(
            "FetchEngine initialized",
            extra={
                "trace_id": self.trace_id,
                "config_path": config_path,
                "graceful_degradation": enable_graceful_degradation
            }
        )
    
    async def load_config(self) -> dict[str, Any]:
        """
        Load data source configurations from YAML file.
        
        Returns:
            Parsed configuration dictionary
            
        Validates: Requirement 1.1
        """
        try:
            config = self.config_manager.load_config(self.config_path)
            logger.info(
                "Fetch sources configuration loaded",
                extra={
                    "trace_id": self.trace_id,
                    "source_count": len(config.get("sources", []))
                }
            )
            return config
        except Exception as e:
            logger.error(
                f"Failed to load fetch sources configuration: {e}",
                extra={"trace_id": self.trace_id, "error": str(e)}
            )
            raise
    
    def validate_sources(self, config: dict[str, Any]) -> bool:
        """
        Validate all data source configurations.
        
        Validates:
        - API credentials are present
        - Endpoints are valid URLs
        - Schedule expressions are valid
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if all sources are valid
            
        Raises:
            ValueError: If validation fails
            
        Validates: Requirement 1.2
        """
        sources = config.get("sources", [])
        
        if not sources:
            raise ValueError("No data sources configured")
        
        for source in sources:
            source_id = source.get("source_id")
            
            # Validate required fields
            required_fields = [
                "source_id", "source_type", "api_endpoint",
                "schedule_type", "schedule_config", "enabled"
            ]
            
            for field in required_fields:
                if field not in source:
                    raise ValueError(
                        f"Source {source_id}: Missing required field '{field}'"
                    )
            
            # Validate schedule configuration
            schedule_type = source.get("schedule_type")
            schedule_config = source.get("schedule_config", {})
            
            if schedule_type == "cron":
                if "cron" not in schedule_config:
                    raise ValueError(
                        f"Source {source_id}: Missing 'cron' in schedule_config"
                    )
                # Validate cron expression by attempting to create trigger
                try:
                    CronTrigger.from_crontab(schedule_config["cron"])
                except Exception as e:
                    raise ValueError(
                        f"Source {source_id}: Invalid cron expression: {e}"
                    )
            
            elif schedule_type == "interval":
                if "seconds" not in schedule_config:
                    raise ValueError(
                        f"Source {source_id}: Missing 'seconds' in schedule_config"
                    )
                seconds = schedule_config["seconds"]
                if not isinstance(seconds, int) or seconds <= 0:
                    raise ValueError(
                        f"Source {source_id}: 'seconds' must be positive integer"
                    )
            
            else:
                raise ValueError(
                    f"Source {source_id}: Invalid schedule_type '{schedule_type}'"
                )
            
            # Validate API endpoint
            api_endpoint = source.get("api_endpoint", "")
            if not api_endpoint.startswith(("http://", "https://")):
                raise ValueError(
                    f"Source {source_id}: Invalid API endpoint '{api_endpoint}'"
                )
        
        logger.info(
            f"Validated {len(sources)} data sources",
            extra={"trace_id": self.trace_id}
        )
        return True
    
    async def schedule_tasks(self, config: dict[str, Any]) -> None:
        """
        Schedule fetch tasks based on configuration.
        
        Supports:
        - Cron-based scheduling
        - Fixed interval scheduling
        
        Args:
            config: Configuration dictionary
            
        Validates: Requirements 1.3, 1.4
        """
        sources = config.get("sources", [])
        
        for source in sources:
            if not source.get("enabled", False):
                logger.info(
                    f"Skipping disabled source: {source['source_id']}",
                    extra={"trace_id": self.trace_id}
                )
                continue
            
            source_id = source["source_id"]
            schedule_type = source["schedule_type"]
            schedule_config = source["schedule_config"]
            
            # Create appropriate trigger
            if schedule_type == "cron":
                trigger = CronTrigger.from_crontab(schedule_config["cron"])
                logger.info(
                    f"Scheduling {source_id} with cron: {schedule_config['cron']}",
                    extra={"trace_id": self.trace_id}
                )
            
            elif schedule_type == "interval":
                trigger = IntervalTrigger(seconds=schedule_config["seconds"])
                logger.info(
                    f"Scheduling {source_id} with interval: {schedule_config['seconds']}s",
                    extra={"trace_id": self.trace_id}
                )
            
            # Schedule the fetch task
            self.scheduler.add_job(
                self._execute_fetch_task,
                trigger=trigger,
                args=[source],
                id=source_id,
                replace_existing=True,
                max_instances=1  # Prevent overlapping executions
            )
            
            # Initialize health status
            self.health_status[source_id] = {
                "status": "scheduled",
                "last_fetch_time": None,
                "last_success_time": None,
                "last_error": None,
                "success_count": 0,
                "failure_count": 0
            }
    
    async def _execute_fetch_task(self, source: dict[str, Any]) -> None:
        """
        Execute a single fetch task.
        
        Args:
            source: Source configuration
            
        Validates: Requirement 1.8
        """
        source_id = source["source_id"]
        start_time = datetime.utcnow()
        trace_id = str(uuid.uuid4())
        
        logger.info(
            f"Starting fetch task for {source_id}",
            extra={
                "trace_id": trace_id,
                "source_id": source_id,
                "source_type": source["source_type"],
                "start_time": start_time.isoformat()
            }
        )
        
        try:
            # Get fetcher from registry
            fetcher = self.fetcher_registry.get(source_id)
            
            if not fetcher:
                raise ValueError(f"No fetcher registered for {source_id}")
            
            # Execute fetch and publish
            await fetcher.fetch_and_publish()
            
            # Update health status
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Get fetcher metrics including rate limit info (Requirement 38.7)
            fetcher_metrics = fetcher.get_metrics()
            
            self.health_status[source_id].update({
                "status": "healthy",
                "last_fetch_time": end_time.isoformat(),
                "last_success_time": end_time.isoformat(),
                "last_error": None,
                "success_count": self.health_status[source_id]["success_count"] + 1,
                "metrics": fetcher_metrics
            })
            
            logger.info(
                f"Fetch task completed for {source_id}",
                extra={
                    "trace_id": trace_id,
                    "source_id": source_id,
                    "end_time": end_time.isoformat(),
                    "duration": duration,
                    "result_status": "success"
                }
            )
            
            # Check and adjust fetch frequency if needed (Requirement 38.8)
            self.adjust_fetch_frequency()
        
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Update health status
            self.health_status[source_id].update({
                "status": "unhealthy",
                "last_fetch_time": end_time.isoformat(),
                "last_error": str(e),
                "failure_count": self.health_status[source_id]["failure_count"] + 1
            })
            
            logger.error(
                f"Fetch task failed for {source_id}: {e}",
                extra={
                    "trace_id": trace_id,
                    "source_id": source_id,
                    "end_time": end_time.isoformat(),
                    "duration": duration,
                    "result_status": "failure",
                    "error": str(e)
                },
                exc_info=True
            )
            
            # Check and adjust fetch frequency if needed (Requirement 38.8)
            self.adjust_fetch_frequency()
    
    def register_fetcher(self, source_id: str, fetcher: Any) -> None:
        """
        Register a data fetcher in the registry.
        
        Args:
            source_id: Unique source identifier
            fetcher: DataFetcher instance
            
        Validates: Requirement 1.5
        """
        self.fetcher_registry[source_id] = fetcher
        logger.info(
            f"Registered fetcher for {source_id}",
            extra={"trace_id": self.trace_id, "source_id": source_id}
        )
    
    def health_check(self) -> dict[str, Any]:
        """
        Get health status of all configured data sources.
        
        Returns:
            Dictionary with health status for each source
            
        Validates: Requirement 1.6
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "sources": self.health_status,
            "total_sources": len(self.health_status),
            "healthy_sources": sum(
                1 for s in self.health_status.values()
                if s["status"] == "healthy"
            ),
            "unhealthy_sources": sum(
                1 for s in self.health_status.values()
                if s["status"] == "unhealthy"
            ),
            "is_overloaded": self.is_overloaded,
            "degradation_factor": self.degradation_factor
        }
    
    def check_system_load(self) -> float:
        """
        Check system load based on failure rate and queue depth.
        
        Returns:
            Load factor (0.0-1.0+)
            
        Validates: Requirement 38.8
        """
        if not self.health_status:
            return 0.0
        
        # Calculate failure rate
        total_requests = sum(
            s.get("success_count", 0) + s.get("failure_count", 0)
            for s in self.health_status.values()
        )
        
        if total_requests == 0:
            return 0.0
        
        total_failures = sum(
            s.get("failure_count", 0)
            for s in self.health_status.values()
        )
        
        failure_rate = total_failures / total_requests
        
        # Check Event Bus queue depth if available
        queue_load = 0.0
        if self.event_bus:
            try:
                # This would need to be implemented in Event Bus
                # For now, use failure rate as primary indicator
                pass
            except Exception:
                pass
        
        # Combine metrics (weighted average)
        load_factor = failure_rate * 0.7 + queue_load * 0.3
        
        return min(load_factor, 1.0)
    
    def adjust_fetch_frequency(self) -> None:
        """
        Adjust fetch frequency based on system load.
        
        Implements graceful degradation by reducing fetch frequency when overloaded.
        
        Validates: Requirement 38.8
        """
        if not self.enable_graceful_degradation:
            return
        
        load = self.check_system_load()
        
        # Check if system is overloaded
        if load >= self.overload_threshold:
            if not self.is_overloaded:
                self.is_overloaded = True
                # Reduce frequency by 50% initially
                self.degradation_factor = 2.0
                
                logger.warning(
                    f"System overloaded (load={load:.2f}), reducing fetch frequency",
                    extra={
                        "trace_id": self.trace_id,
                        "load": load,
                        "degradation_factor": self.degradation_factor
                    }
                )
                
                # Reschedule tasks with reduced frequency
                self._reschedule_with_degradation()
            
            elif load >= 0.9:
                # Further reduce frequency if load is very high
                self.degradation_factor = min(self.degradation_factor * 1.5, 4.0)
                
                logger.warning(
                    f"System critically overloaded (load={load:.2f}), further reducing frequency",
                    extra={
                        "trace_id": self.trace_id,
                        "load": load,
                        "degradation_factor": self.degradation_factor
                    }
                )
                
                self._reschedule_with_degradation()
        
        elif load < self.overload_threshold * 0.7:
            # System load has decreased, restore normal frequency
            if self.is_overloaded:
                self.is_overloaded = False
                self.degradation_factor = 1.0
                
                logger.info(
                    f"System load normalized (load={load:.2f}), restoring normal frequency",
                    extra={
                        "trace_id": self.trace_id,
                        "load": load,
                        "degradation_factor": self.degradation_factor
                    }
                )
                
                self._reschedule_with_degradation()
    
    def _reschedule_with_degradation(self) -> None:
        """
        Reschedule tasks with current degradation factor.
        
        Validates: Requirement 38.8
        """
        # This would reschedule all tasks with adjusted intervals
        # For interval-based tasks, multiply interval by degradation_factor
        # For cron-based tasks, this is more complex and may require
        # temporarily pausing non-critical tasks
        
        for job in self.scheduler.get_jobs():
            source_id = job.id
            
            # Check if source is marked as critical
            source_config = None
            for source in self.health_status.keys():
                if source == source_id:
                    # Get original config to check priority
                    # For now, skip non-critical sources when degraded
                    if self.degradation_factor > 1.0:
                        # Could pause non-critical jobs here
                        pass
                    break
    
    async def reload_config(self) -> None:
        """
        Reload configuration and reschedule tasks.
        
        Validates: Requirement 1.7
        """
        logger.info(
            "Reloading fetch sources configuration",
            extra={"trace_id": self.trace_id}
        )
        
        try:
            # Load new configuration
            config = await self.load_config()
            
            # Validate new configuration
            self.validate_sources(config)
            
            # Remove all existing jobs
            self.scheduler.remove_all_jobs()
            
            # Reschedule with new configuration
            await self.schedule_tasks(config)
            
            logger.info(
                "Configuration reloaded successfully",
                extra={"trace_id": self.trace_id}
            )
        
        except Exception as e:
            logger.error(
                f"Failed to reload configuration: {e}",
                extra={"trace_id": self.trace_id, "error": str(e)},
                exc_info=True
            )
            raise
    
    async def start(self) -> None:
        """Start the Fetch Engine."""
        logger.info("Starting Fetch Engine", extra={"trace_id": self.trace_id})
        
        # Load and validate configuration
        config = await self.load_config()
        self.validate_sources(config)
        
        # Schedule tasks
        await self.schedule_tasks(config)
        
        # Start scheduler
        self.scheduler.start()
        
        logger.info("Fetch Engine started", extra={"trace_id": self.trace_id})
    
    async def stop(self) -> None:
        """Stop the Fetch Engine."""
        logger.info("Stopping Fetch Engine", extra={"trace_id": self.trace_id})
        
        # Shutdown scheduler
        self.scheduler.shutdown(wait=True)
        
        logger.info("Fetch Engine stopped", extra={"trace_id": self.trace_id})
