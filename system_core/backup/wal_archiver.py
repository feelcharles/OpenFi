"""
WAL (Write-Ahead Log) archiving for point-in-time recovery.

Implements PostgreSQL WAL archiving to enable point-in-time recovery (PITR).
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from system_core.backup.storage_adapter import StorageAdapter

logger = logging.getLogger(__name__)

class WALArchiver:
    """
    Manages PostgreSQL WAL archiving for point-in-time recovery.
    
    Features:
    - Archive WAL files to remote storage
    - Configure PostgreSQL for continuous archiving
    - Support point-in-time recovery
    - Monitor WAL archive status
    """
    
    def __init__(
        self,
        storage_adapter: StorageAdapter,
        wal_archive_dir: str = "backups/wal_archive",
        db_host: str = "localhost",
        db_port: int = 5432,
        db_user: str = "OpenFi",
        db_password: str = "",
    ):
        """
        Initialize WAL archiver.
        
        Args:
            storage_adapter: Storage adapter for WAL files
            wal_archive_dir: Local directory for WAL archive
            db_host: Database host
            db_port: Database port
            db_user: Database user
            db_password: Database password
        """
        self.storage_adapter = storage_adapter
        self.wal_archive_dir = Path(wal_archive_dir)
        self.wal_archive_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_password = db_password
        
        logger.info(f"WAL archiver initialized with archive dir: {self.wal_archive_dir}")
    
    async def archive_wal_file(self, wal_file: str) -> dict[str, Any]:
        """
        Archive a WAL file to remote storage.
        
        This method is called by PostgreSQL's archive_command.
        
        Args:
            wal_file: Path to WAL file
            
        Returns:
            Archive result with status
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        wal_filename = Path(wal_file).name
        
        logger.info(f"Archiving WAL file: {wal_filename}")
        
        try:
            # Copy WAL file to local archive directory
            local_archive_path = self.wal_archive_dir / wal_filename
            
            # Use subprocess to copy (more reliable than shutil for large files)
            if os.name == 'nt':  # Windows
                cmd = ['copy', wal_file, str(local_archive_path)]
            else:  # Unix/Linux
                cmd = ['cp', wal_file, str(local_archive_path)]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                shell=(os.name == 'nt')
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to copy WAL file: {result.stderr}")
                return {
                    'status': 'failed',
                    'error': result.stderr,
                    'wal_file': wal_filename,
                }
            
            # Upload to remote storage
            remote_path = f"wal_archive/{wal_filename}"
            upload_success = await self.storage_adapter.upload(
                str(local_archive_path),
                remote_path,
                encrypt=True
            )
            
            if not upload_success:
                logger.error(f"Failed to upload WAL file to remote storage")
                return {
                    'status': 'failed',
                    'error': 'Upload to remote storage failed',
                    'wal_file': wal_filename,
                }
            
            # Clean up local copy (keep only recent files)
            await self._cleanup_local_wal_files()
            
            logger.info(f"WAL file archived successfully: {wal_filename}")
            
            return {
                'status': 'success',
                'wal_file': wal_filename,
                'remote_path': remote_path,
                'timestamp': timestamp,
            }
            
        except Exception as e:
            logger.error(f"Failed to archive WAL file {wal_filename}: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'wal_file': wal_filename,
            }
    
    async def _cleanup_local_wal_files(self, keep_count: int = 10):
        """
        Clean up old local WAL files, keeping only recent ones.
        
        Args:
            keep_count: Number of recent WAL files to keep
        """
        try:
            wal_files = sorted(
                self.wal_archive_dir.glob('*'),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            # Delete old files beyond keep_count
            for wal_file in wal_files[keep_count:]:
                wal_file.unlink()
                logger.debug(f"Deleted old local WAL file: {wal_file.name}")
                
        except Exception as e:
            logger.warning(f"Failed to cleanup local WAL files: {e}")
    
    def get_archive_command(self) -> str:
        """
        Get the PostgreSQL archive_command configuration.
        
        Returns:
            Archive command string for postgresql.conf
        """
        # Get the path to the archive script
        script_path = Path(__file__).parent / "archive_wal.py"
        
        # Command that PostgreSQL will execute
        # %p = path of file to archive
        # %f = file name only
        archive_command = f"python {script_path} %p %f"
        
        return archive_command
    
    def get_postgresql_config(self) -> dict[str, str]:
        """
        Get recommended PostgreSQL configuration for WAL archiving.
        
        Returns:
            Dictionary of postgresql.conf settings
        """
        return {
            'wal_level': 'replica',  # or 'logical' for logical replication
            'archive_mode': 'on',
            'archive_command': self.get_archive_command(),
            'archive_timeout': '300',  # Archive every 5 minutes
            'max_wal_senders': '3',
            'wal_keep_size': '1GB',  # PostgreSQL 13+
        }
    
    async def restore_wal_file(self, wal_filename: str, restore_path: str) -> bool:
        """
        Restore a WAL file from remote storage.
        
        This is used during point-in-time recovery.
        
        Args:
            wal_filename: Name of WAL file to restore
            restore_path: Path where to restore the file
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Restoring WAL file: {wal_filename}")
        
        try:
            remote_path = f"wal_archive/{wal_filename}"
            
            download_success = await self.storage_adapter.download(
                remote_path,
                restore_path,
                decrypt=True
            )
            
            if download_success:
                logger.info(f"WAL file restored: {wal_filename}")
                return True
            else:
                logger.error(f"Failed to restore WAL file: {wal_filename}")
                return False
                
        except Exception as e:
            logger.error(f"Error restoring WAL file {wal_filename}: {e}")
            return False
    
    def get_restore_command(self) -> str:
        """
        Get the restore_command for recovery.conf.
        
        Returns:
            Restore command string
        """
        script_path = Path(__file__).parent / "restore_wal.py"
        
        # Command that PostgreSQL will execute during recovery
        # %f = file name only
        # %p = path to copy file to
        restore_command = f"python {script_path} %f %p"
        
        return restore_command
    
    async def create_recovery_config(
        self,
        target_time: Optional[str] = None,
        target_xid: Optional[str] = None,
        target_name: Optional[str] = None,
    ) -> str:
        """
        Create recovery configuration for point-in-time recovery.
        
        Args:
            target_time: Target timestamp (e.g., '2024-01-15 14:30:00')
            target_xid: Target transaction ID
            target_name: Target restore point name
            
        Returns:
            Recovery configuration content
        """
        config_lines = [
            "# Recovery configuration for point-in-time recovery",
            f"restore_command = '{self.get_restore_command()}'",
        ]
        
        if target_time:
            config_lines.append(f"recovery_target_time = '{target_time}'")
        elif target_xid:
            config_lines.append(f"recovery_target_xid = '{target_xid}'")
        elif target_name:
            config_lines.append(f"recovery_target_name = '{target_name}'")
        
        config_lines.extend([
            "recovery_target_action = 'promote'",
            "recovery_target_inclusive = true",
        ])
        
        return '\n'.join(config_lines)
    
    async def get_wal_archive_status(self) -> dict[str, Any]:
        """
        Get WAL archive status and statistics.
        
        Returns:
            Status information
        """
        try:
            # List WAL files in remote storage
            wal_files = await self.storage_adapter.list_files('wal_archive/')
            
            # Get local WAL files
            local_wal_files = list(self.wal_archive_dir.glob('*'))
            
            return {
                'status': 'active',
                'remote_wal_count': len(wal_files),
                'local_wal_count': len(local_wal_files),
                'archive_dir': str(self.wal_archive_dir),
                'timestamp': datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to get WAL archive status: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat(),
            }

# Standalone script functions for PostgreSQL to call

async def archive_wal_standalone(wal_path: str, wal_filename: str):
    """
    Standalone function to archive WAL file.
    Called by PostgreSQL archive_command.
    """
    from system_core.backup.storage_adapter import LocalStorageAdapter
    
    storage = LocalStorageAdapter()
    archiver = WALArchiver(storage)
    
    result = await archiver.archive_wal_file(wal_path)
    
    if result['status'] == 'success':
        return 0  # Success exit code
    else:
        return 1  # Failure exit code

async def restore_wal_standalone(wal_filename: str, restore_path: str):
    """
    Standalone function to restore WAL file.
    Called by PostgreSQL restore_command.
    """
    from system_core.backup.storage_adapter import LocalStorageAdapter
    
    storage = LocalStorageAdapter()
    archiver = WALArchiver(storage)
    
    success = await archiver.restore_wal_file(wal_filename, restore_path)
    
    if success:
        return 0  # Success exit code
    else:
        return 1  # Failure exit code
