"""
Backup and disaster recovery module for OpenFi Lite.

This module provides automated backup functionality for PostgreSQL database,
configuration files, and EA files with remote storage support.
"""

from system_core.backup.backup_manager import BackupManager
from system_core.backup.storage_adapter import StorageAdapter, S3StorageAdapter, LocalStorageAdapter

__all__ = [
    'BackupManager',
    'StorageAdapter',
    'S3StorageAdapter',
    'LocalStorageAdapter',
]
