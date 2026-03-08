"""
Data retention and cleanup job.

Validates: Requirements 29.1, 29.2, 29.3, 29.4, 29.5, 29.6, 29.7
"""

import os
import gzip
import json
import shutil
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio

import yaml
from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from system_core.monitoring.logger import get_logger
from system_core.database.models import Signal, Trade, Notification

logger = get_logger(__name__)

@dataclass
class RetentionPolicy:
    """Retention policy configuration."""
    data_type: str
    retention_days: int
    archive_before_delete: bool = False
    archive_format: str = "gzip"
    soft_delete: bool = False
    description: str = ""

@dataclass
class CleanupResult:
    """Result of cleanup operation."""
    data_type: str
    records_deleted: int
    records_archived: int
    storage_freed: int  # bytes
    duration: float  # seconds
    errors: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "data_type": self.data_type,
            "records_deleted": self.records_deleted,
            "records_archived": self.records_archived,
            "storage_freed_mb": round(self.storage_freed / (1024 * 1024), 2),
            "duration_seconds": round(self.duration, 2),
            "errors": self.errors
        }

class CleanupJob:
    """
    Data retention and cleanup job.
    
    Validates: Requirements 29.1, 29.2, 29.3, 29.4, 29.5, 29.6, 29.7
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        config_path: str = "config/retention_policy.yaml"
    ):
        """
        Initialize cleanup job.
        
        Args:
            db_session: Database session
            config_path: Path to retention policy configuration
        """
        self.db = db_session
        self.config_path = config_path
        self.policies: list[RetentionPolicy] = []
        self.archive_base_dir = Path("archive")
        self.scheduler: Optional[AsyncIOScheduler] = None
        
        # Load configuration
        self._load_config()
    
    def _load_config(self) -> None:
        """
        Load retention policy configuration.
        
        Validates: Requirements 29.1, 29.2
        """
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Parse policies
            self.policies = []
            for policy_config in config.get('policies', []):
                policy = RetentionPolicy(
                    data_type=policy_config['data_type'],
                    retention_days=policy_config['retention_days'],
                    archive_before_delete=policy_config.get('archive_before_delete', False),
                    archive_format=policy_config.get('archive_format', 'gzip'),
                    soft_delete=policy_config.get('soft_delete', False),
                    description=policy_config.get('description', '')
                )
                self.policies.append(policy)
            
            # Parse archive settings
            archive_config = config.get('archive', {})
            self.archive_base_dir = Path(archive_config.get('base_directory', 'archive'))
            self.archive_base_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(
                "retention_policy_loaded",
                policy_count=len(self.policies),
                archive_dir=str(self.archive_base_dir)
            )
            
        except Exception as e:
            logger.error(
                "retention_policy_load_error",
                exception_type=type(e).__name__,
                exception_message=str(e)
            )
            raise
    
    def start_scheduled_cleanup(self) -> None:
        """
        Start scheduled cleanup job.
        
        Runs daily at 03:00 UTC by default.
        
        Validates: Requirements 29.3
        """
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            schedule_config = config.get('cleanup_schedule', {})
            
            if not schedule_config.get('enabled', True):
                logger.info("cleanup_schedule_disabled")
                return
            
            cron_expr = schedule_config.get('cron', '0 3 * * *')
            
            # Create scheduler
            self.scheduler = AsyncIOScheduler()
            
            # Add job
            self.scheduler.add_job(
                self.run_cleanup,
                trigger=CronTrigger.from_crontab(cron_expr),
                id='cleanup_job',
                name='Data Retention Cleanup',
                replace_existing=True
            )
            
            # Start scheduler
            self.scheduler.start()
            
            logger.info(
                "cleanup_schedule_started",
                cron=cron_expr
            )
            
        except Exception as e:
            logger.error(
                "cleanup_schedule_start_error",
                exception_type=type(e).__name__,
                exception_message=str(e)
            )
    
    def stop_scheduled_cleanup(self) -> None:
        """Stop scheduled cleanup job."""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("cleanup_schedule_stopped")
    
    async def run_cleanup(self) -> dict[str, Any]:
        """
        Run cleanup for all policies.
        
        Returns:
            Dict containing cleanup results
            
        Validates: Requirements 29.3, 29.4, 29.6, 29.7
        """
        start_time = datetime.utcnow()
        logger.info("cleanup_job_started")
        
        results = []
        total_deleted = 0
        total_archived = 0
        total_freed = 0
        
        for policy in self.policies:
            try:
                result = await self._cleanup_data_type(policy)
                results.append(result)
                total_deleted += result.records_deleted
                total_archived += result.records_archived
                total_freed += result.storage_freed
                
            except Exception as e:
                logger.error(
                    "cleanup_policy_error",
                    data_type=policy.data_type,
                    exception_type=type(e).__name__,
                    exception_message=str(e)
                )
                results.append(CleanupResult(
                    data_type=policy.data_type,
                    records_deleted=0,
                    records_archived=0,
                    storage_freed=0,
                    duration=0.0,
                    errors=[str(e)]
                ))
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        summary = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": round(duration, 2),
            "total_records_deleted": total_deleted,
            "total_records_archived": total_archived,
            "total_storage_freed_mb": round(total_freed / (1024 * 1024), 2),
            "results": [r.to_dict() for r in results]
        }
        
        logger.info(
            "cleanup_job_completed",
            duration=duration,
            deleted=total_deleted,
            archived=total_archived,
            freed_mb=round(total_freed / (1024 * 1024), 2)
        )
        
        return summary
    
    async def _cleanup_data_type(self, policy: RetentionPolicy) -> CleanupResult:
        """
        Cleanup data for specific policy.
        
        Args:
            policy: Retention policy
            
        Returns:
            CleanupResult: Cleanup result
        """
        start_time = datetime.utcnow()
        cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_days)
        
        logger.info(
            "cleanup_policy_started",
            data_type=policy.data_type,
            retention_days=policy.retention_days,
            cutoff_date=cutoff_date.isoformat()
        )
        
        records_deleted = 0
        records_archived = 0
        storage_freed = 0
        errors = []
        
        try:
            # Get records to delete
            if policy.data_type == "analyzed_signals":
                records = await self._get_old_signals(cutoff_date, policy.soft_delete)
            elif policy.data_type == "trade_records":
                records = await self._get_old_trades(cutoff_date, policy.soft_delete)
            elif policy.data_type == "notifications":
                records = await self._get_old_notifications(cutoff_date)
            else:
                logger.warning(
                    "cleanup_policy_not_implemented",
                    data_type=policy.data_type
                )
                records = []
            
            # Archive if configured
            if policy.archive_before_delete and records:
                archived_count, archived_size = await self._archive_records(
                    policy.data_type,
                    records,
                    policy.archive_format
                )
                records_archived = archived_count
                storage_freed = archived_size
            
            # Delete records
            if policy.soft_delete:
                deleted_count = await self._soft_delete_records(records)
            else:
                deleted_count = await self._hard_delete_records(records)
            
            records_deleted = deleted_count
            
        except Exception as e:
            errors.append(str(e))
            logger.error(
                "cleanup_policy_execution_error",
                data_type=policy.data_type,
                exception_type=type(e).__name__,
                exception_message=str(e)
            )
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        return CleanupResult(
            data_type=policy.data_type,
            records_deleted=records_deleted,
            records_archived=records_archived,
            storage_freed=storage_freed,
            duration=duration,
            errors=errors
        )
    
    async def _get_old_signals(
        self,
        cutoff_date: datetime,
        soft_delete: bool
    ) -> list[Signal]:
        """Get signals older than cutoff date."""
        query = self.db.query(Signal).filter(
            Signal.created_at < cutoff_date
        )
        
        if soft_delete:
            # Only get records not already soft-deleted
            query = query.filter(Signal.deleted_at.is_(None))
        
        return query.limit(1000).all()
    
    async def _get_old_trades(
        self,
        cutoff_date: datetime,
        soft_delete: bool
    ) -> list[Trade]:
        """Get trades older than cutoff date."""
        query = self.db.query(Trade).filter(
            Trade.execution_time < cutoff_date
        )
        
        if soft_delete:
            query = query.filter(Trade.deleted_at.is_(None))
        
        return query.limit(1000).all()
    
    async def _get_old_notifications(
        self,
        cutoff_date: datetime
    ) -> list[Notification]:
        """Get notifications older than cutoff date."""
        return self.db.query(Notification).filter(
            Notification.created_at < cutoff_date
        ).limit(1000).all()
    
    async def _archive_records(
        self,
        data_type: str,
        records: list[Any],
        archive_format: str
    ) -> tuple[int, int]:
        """
        Archive records to compressed files.
        
        Args:
            data_type: Data type name
            records: Records to archive
            archive_format: Archive format (gzip)
            
        Returns:
            Tuple of (archived_count, archived_size_bytes)
            
        Validates: Requirements 29.4
        """
        if not records:
            return 0, 0
        
        # Create archive directory structure
        now = datetime.utcnow()
        archive_dir = self.archive_base_dir / data_type / str(now.year) / f"{now.month:02d}"
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Create archive filename
        archive_file = archive_dir / f"{data_type}_{now.strftime('%Y%m%d_%H%M%S')}.json.gz"
        
        # Serialize records
        records_data = []
        for record in records:
            # Convert SQLAlchemy model to dict
            record_dict = {
                column.name: getattr(record, column.name)
                for column in record.__table__.columns
            }
            # Convert datetime to ISO format
            for key, value in record_dict.items():
                if isinstance(value, datetime):
                    record_dict[key] = value.isoformat()
            records_data.append(record_dict)
        
        # Write to compressed file
        json_data = json.dumps(records_data, indent=2)
        
        with gzip.open(archive_file, 'wt', encoding='utf-8') as f:
            f.write(json_data)
        
        # Get file size
        file_size = archive_file.stat().st_size
        
        logger.info(
            "records_archived",
            data_type=data_type,
            count=len(records),
            file=str(archive_file),
            size_mb=round(file_size / (1024 * 1024), 2)
        )
        
        return len(records), file_size
    
    async def _soft_delete_records(self, records: list[Any]) -> int:
        """
        Soft delete records by setting deleted_at timestamp.
        
        Args:
            records: Records to soft delete
            
        Returns:
            Number of records soft deleted
            
        Validates: Requirements 29.5
        """
        if not records:
            return 0
        
        count = 0
        now = datetime.utcnow()
        
        for record in records:
            if hasattr(record, 'deleted_at'):
                record.deleted_at = now
                count += 1
        
        self.db.commit()
        
        logger.info(
            "records_soft_deleted",
            count=count
        )
        
        return count
    
    async def _hard_delete_records(self, records: list[Any]) -> int:
        """
        Hard delete records from database.
        
        Args:
            records: Records to delete
            
        Returns:
            Number of records deleted
        """
        if not records:
            return 0
        
        count = len(records)
        
        for record in records:
            self.db.delete(record)
        
        self.db.commit()
        
        logger.info(
            "records_hard_deleted",
            count=count
        )
        
        return count

