"""
Backup manager for automated database, configuration, and EA file backups.

Implements automated backup scheduling, retention policies, and remote storage.
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any
import shutil
import tarfile

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from system_core.backup.storage_adapter import StorageAdapter, LocalStorageAdapter
from system_core.backup.backup_verifier import BackupVerifier
from system_core.config.settings import get_settings

logger = logging.getLogger(__name__)

class BackupManager:
    """
    Manages automated backups for database, configuration, and EA files.
    
    Features:
    - Daily PostgreSQL backups at 02:00 UTC using pg_dump
    - Retention policy: daily (7 days), weekly (4 weeks), monthly (12 months)
    - Remote storage with encryption
    - Backup verification
    - Point-in-time recovery support via WAL archiving
    """
    
    def __init__(
        self,
        storage_adapter: Optional[StorageAdapter] = None,
        backup_dir: str = "backups",
        db_host: Optional[str] = None,
        db_port: Optional[int] = None,
        db_name: Optional[str] = None,
        db_user: Optional[str] = None,
        db_password: Optional[str] = None,
    ):
        """
        Initialize backup manager.
        
        Args:
            storage_adapter: Storage adapter for remote backups
            backup_dir: Local directory for temporary backup files
            db_host: Database host
            db_port: Database port
            db_name: Database name
            db_user: Database user
            db_password: Database password
        """
        self.storage_adapter = storage_adapter or LocalStorageAdapter(backup_dir)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Database connection details
        settings = get_settings()
        self.db_host = db_host or os.getenv('DB_HOST', 'localhost')
        self.db_port = db_port or int(os.getenv('DB_PORT', '5432'))
        self.db_name = db_name or os.getenv('DB_NAME', 'system_core')
        self.db_user = db_user or os.getenv('DB_USER', 'OpenFi')
        self.db_password = db_password or os.getenv('DB_PASSWORD', '')
        
        # Backup verifier
        self.verifier = BackupVerifier(
            storage_adapter=self.storage_adapter,
            db_host=self.db_host,
            db_port=self.db_port,
            db_user=self.db_user,
            db_password=self.db_password,
        )
        
        # Scheduler for automated backups
        self.scheduler = AsyncIOScheduler()
        
        # Retention policy (in days)
        self.retention_policy = {
            'daily': 7,
            'weekly': 28,  # 4 weeks
            'monthly': 365,  # 12 months
        }
        
        logger.info(
            f"Backup manager initialized with storage adapter: {type(self.storage_adapter).__name__}"
        )
    
    def start(self):
        """Start automated backup scheduler."""
        # Schedule daily database backup at 02:00 UTC
        self.scheduler.add_job(
            self.backup_database,
            trigger=CronTrigger(hour=2, minute=0, timezone='UTC'),
            id='daily_database_backup',
            name='Daily Database Backup',
            replace_existing=True,
        )
        
        # Schedule daily config and EA backup at 02:30 UTC
        self.scheduler.add_job(
            self.backup_config_and_ea,
            trigger=CronTrigger(hour=2, minute=30, timezone='UTC'),
            id='daily_config_ea_backup',
            name='Daily Config and EA Backup',
            replace_existing=True,
        )
        
        # Schedule weekly cleanup at 03:00 UTC on Sundays
        self.scheduler.add_job(
            self.cleanup_old_backups,
            trigger=CronTrigger(day_of_week='sun', hour=3, minute=0, timezone='UTC'),
            id='weekly_backup_cleanup',
            name='Weekly Backup Cleanup',
            replace_existing=True,
        )
        
        # Schedule weekly backup verification at 04:00 UTC on Sundays
        self.scheduler.add_job(
            self.verify_latest_backup,
            trigger=CronTrigger(day_of_week='sun', hour=4, minute=0, timezone='UTC'),
            id='weekly_backup_verification',
            name='Weekly Backup Verification',
            replace_existing=True,
        )
        
        self.scheduler.start()
        logger.info("Backup scheduler started")
    
    async def initialize(self):
        """
        Initialize backup manager (alias for start).
        
        This method is provided for backward compatibility.
        """
        self.start()
    
    async def close(self):
        """
        Close backup manager (alias for stop).
        
        This method is provided for backward compatibility.
        """
        self.stop()
    
    def get_config(self) -> dict:
        """
        Get backup configuration.
        
        Returns:
            Configuration dictionary
        """
        return {
            'backup_dir': str(self.backup_dir),
            'db_host': self.db_host,
            'db_port': self.db_port,
            'db_name': self.db_name,
            'retention_policy': self.retention_policy,
            'storage_adapter': type(self.storage_adapter).__name__,
        }
    
    def stop(self):
        """Stop automated backup scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Backup scheduler stopped")
    
    async def backup_database(self) -> dict[str, Any]:
        """
        Perform PostgreSQL database backup using pg_dump.
        
        Returns:
            Backup result with status, file path, and metadata
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"db_backup_{timestamp}.sql"
        backup_path = self.backup_dir / backup_filename
        
        logger.info(f"Starting database backup: {backup_filename}")
        
        try:
            # Set PGPASSWORD environment variable for pg_dump
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_password
            
            # Run pg_dump
            cmd = [
                'pg_dump',
                '-h', self.db_host,
                '-p', str(self.db_port),
                '-U', self.db_user,
                '-d', self.db_name,
                '-F', 'p',  # Plain text format
                '-f', str(backup_path),
                '--no-owner',
                '--no-acl',
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes timeout
            )
            
            if result.returncode != 0:
                logger.error(f"pg_dump failed: {result.stderr}")
                return {
                    'status': 'failed',
                    'error': result.stderr,
                    'timestamp': timestamp,
                }
            
            # Get backup file size
            backup_size = backup_path.stat().st_size
            
            # Determine backup type (daily, weekly, monthly)
            backup_type = self._determine_backup_type()
            
            # Upload to remote storage
            remote_path = f"database/{backup_type}/{backup_filename}"
            upload_success = await self.storage_adapter.upload(
                str(backup_path),
                remote_path,
                encrypt=True
            )
            
            if not upload_success:
                logger.error(f"Failed to upload backup to remote storage")
                return {
                    'status': 'failed',
                    'error': 'Upload to remote storage failed',
                    'timestamp': timestamp,
                    'local_path': str(backup_path),
                }
            
            # Clean up local backup file
            backup_path.unlink()
            
            logger.info(
                f"Database backup completed: {backup_filename} "
                f"({backup_size / 1024 / 1024:.2f} MB, type: {backup_type})"
            )
            
            return {
                'status': 'success',
                'timestamp': timestamp,
                'backup_type': backup_type,
                'filename': backup_filename,
                'remote_path': remote_path,
                'size_bytes': backup_size,
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Database backup timed out after 10 minutes")
            return {
                'status': 'failed',
                'error': 'Backup timed out',
                'timestamp': timestamp,
            }
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'timestamp': timestamp,
            }
    
    async def backup_config_and_ea(self) -> dict[str, Any]:
        """
        Backup configuration files and EA files.
        
        Returns:
            Backup result with status and metadata
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"config_ea_backup_{timestamp}.tar.gz"
        backup_path = self.backup_dir / backup_filename
        
        logger.info(f"Starting config and EA backup: {backup_filename}")
        
        try:
            # Create tar.gz archive
            with tarfile.open(backup_path, 'w:gz') as tar:
                # Add config directory
                if Path('config').exists():
                    tar.add('config', arcname='config')
                
                # Add EA directory
                if Path('ea').exists():
                    tar.add('ea', arcname='ea')
            
            # Get backup file size
            backup_size = backup_path.stat().st_size
            
            # Determine backup type
            backup_type = self._determine_backup_type()
            
            # Upload to remote storage
            remote_path = f"config_ea/{backup_type}/{backup_filename}"
            upload_success = await self.storage_adapter.upload(
                str(backup_path),
                remote_path,
                encrypt=True
            )
            
            if not upload_success:
                logger.error(f"Failed to upload config/EA backup to remote storage")
                return {
                    'status': 'failed',
                    'error': 'Upload to remote storage failed',
                    'timestamp': timestamp,
                    'local_path': str(backup_path),
                }
            
            # Clean up local backup file
            backup_path.unlink()
            
            logger.info(
                f"Config and EA backup completed: {backup_filename} "
                f"({backup_size / 1024 / 1024:.2f} MB, type: {backup_type})"
            )
            
            return {
                'status': 'success',
                'timestamp': timestamp,
                'backup_type': backup_type,
                'filename': backup_filename,
                'remote_path': remote_path,
                'size_bytes': backup_size,
            }
            
        except Exception as e:
            logger.error(f"Config and EA backup failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'timestamp': timestamp,
            }
    
    def _determine_backup_type(self) -> str:
        """
        Determine backup type based on current date.
        
        Returns:
            'daily', 'weekly', or 'monthly'
        """
        now = datetime.utcnow()
        
        # Monthly backup on the 1st of each month
        if now.day == 1:
            return 'monthly'
        
        # Weekly backup on Sundays
        if now.weekday() == 6:  # Sunday
            return 'weekly'
        
        # Daily backup
        return 'daily'
    
    async def cleanup_old_backups(self) -> dict[str, Any]:
        """
        Clean up old backups according to retention policy.
        
        Returns:
            Cleanup result with counts of deleted backups
        """
        logger.info("Starting backup cleanup")
        
        deleted_counts = {
            'daily': 0,
            'weekly': 0,
            'monthly': 0,
        }
        
        try:
            # Clean up database backups
            for backup_type, retention_days in self.retention_policy.items():
                prefix = f"database/{backup_type}/"
                files = await self.storage_adapter.list_files(prefix)
                
                cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
                
                for file_path in files:
                    # Extract timestamp from filename
                    try:
                        filename = Path(file_path).name
                        # Format: db_backup_YYYYMMDD_HHMMSS.sql.gz
                        timestamp_str = filename.split('_')[2] + '_' + filename.split('_')[3].split('.')[0]
                        file_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        
                        if file_date < cutoff_date:
                            await self.storage_adapter.delete(file_path)
                            deleted_counts[backup_type] += 1
                            logger.info(f"Deleted old backup: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to parse or delete backup {file_path}: {e}")
            
            # Clean up config/EA backups
            for backup_type, retention_days in self.retention_policy.items():
                prefix = f"config_ea/{backup_type}/"
                files = await self.storage_adapter.list_files(prefix)
                
                cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
                
                for file_path in files:
                    try:
                        filename = Path(file_path).name
                        # Format: config_ea_backup_YYYYMMDD_HHMMSS.tar.gz
                        timestamp_str = filename.split('_')[3] + '_' + filename.split('_')[4].split('.')[0]
                        file_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        
                        if file_date < cutoff_date:
                            await self.storage_adapter.delete(file_path)
                            deleted_counts[backup_type] += 1
                            logger.info(f"Deleted old backup: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to parse or delete backup {file_path}: {e}")
            
            logger.info(f"Backup cleanup completed: {deleted_counts}")
            
            return {
                'status': 'success',
                'deleted_counts': deleted_counts,
                'timestamp': datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat(),
            }
    
    async def list_backups(self, backup_category: str = 'database') -> list[dict[str, Any]]:
        """
        List available backups.
        
        Args:
            backup_category: 'database' or 'config_ea'
            
        Returns:
            List of backup metadata
        """
        backups = []
        
        try:
            for backup_type in ['daily', 'weekly', 'monthly']:
                prefix = f"{backup_category}/{backup_type}/"
                files = await self.storage_adapter.list_files(prefix)
                
                for file_path in files:
                    try:
                        filename = Path(file_path).name
                        
                        # Parse timestamp
                        if backup_category == 'database':
                            timestamp_str = filename.split('_')[2] + '_' + filename.split('_')[3].split('.')[0]
                        else:
                            timestamp_str = filename.split('_')[3] + '_' + filename.split('_')[4].split('.')[0]
                        
                        file_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                        
                        backups.append({
                            'filename': filename,
                            'remote_path': file_path,
                            'backup_type': backup_type,
                            'timestamp': file_date.isoformat(),
                            'category': backup_category,
                        })
                    except Exception as e:
                        logger.warning(f"Failed to parse backup metadata for {file_path}: {e}")
            
            # Sort by timestamp descending
            backups.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    async def restore_database(self, backup_path: str, target_db: Optional[str] = None) -> dict[str, Any]:
        """
        Restore database from backup.
        
        Args:
            backup_path: Remote path to backup file
            target_db: Target database name (defaults to main database)
            
        Returns:
            Restore result with status
        """
        target_db = target_db or self.db_name
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        
        logger.info(f"Starting database restore from {backup_path} to {target_db}")
        
        try:
            # Download backup file
            local_backup = self.backup_dir / f"restore_{timestamp}.sql"
            download_success = await self.storage_adapter.download(
                backup_path,
                str(local_backup),
                decrypt=True
            )
            
            if not download_success:
                return {
                    'status': 'failed',
                    'error': 'Failed to download backup file',
                    'timestamp': timestamp,
                }
            
            # Set PGPASSWORD environment variable
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_password
            
            # Run psql to restore
            cmd = [
                'psql',
                '-h', self.db_host,
                '-p', str(self.db_port),
                '-U', self.db_user,
                '-d', target_db,
                '-f', str(local_backup),
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes timeout
            )
            
            # Clean up local file
            local_backup.unlink()
            
            if result.returncode != 0:
                logger.error(f"Database restore failed: {result.stderr}")
                return {
                    'status': 'failed',
                    'error': result.stderr,
                    'timestamp': timestamp,
                }
            
            logger.info(f"Database restore completed successfully to {target_db}")
            
            return {
                'status': 'success',
                'timestamp': timestamp,
                'target_db': target_db,
                'backup_path': backup_path,
            }
            
        except subprocess.TimeoutExpired:
            logger.error("Database restore timed out after 10 minutes")
            return {
                'status': 'failed',
                'error': 'Restore timed out',
                'timestamp': timestamp,
            }
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'timestamp': timestamp,
            }
    
    async def verify_latest_backup(self) -> dict[str, Any]:
        """
        Verify the latest database backup.
        
        Returns:
            Verification result
        """
        logger.info("Starting verification of latest backup")
        
        try:
            # Get list of database backups
            backups = await self.list_backups('database')
            
            if not backups:
                logger.warning("No backups found to verify")
                return {
                    'status': 'failed',
                    'error': 'No backups found',
                    'timestamp': datetime.utcnow().isoformat(),
                }
            
            # Get the most recent backup
            latest_backup = backups[0]
            
            # Verify the backup
            verification_result = await self.verifier.verify_backup(
                latest_backup['remote_path']
            )
            
            logger.info(
                f"Latest backup verification completed: {verification_result['status']}"
            )
            
            return verification_result
            
        except Exception as e:
            logger.error(f"Failed to verify latest backup: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat(),
            }

# Global backup manager instance
_backup_manager: Optional[BackupManager] = None

def get_backup_manager() -> BackupManager:
    """Get or create global backup manager instance."""
    global _backup_manager
    
    if _backup_manager is None:
        _backup_manager = BackupManager()
    
    return _backup_manager
