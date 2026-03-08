"""
Storage adapters for backup files.

Supports multiple storage backends: S3, GCS, Azure Blob, and local filesystem.
"""

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from datetime import datetime
import gzip
import shutil

logger = logging.getLogger(__name__)

class StorageAdapter(ABC):
    """Abstract base class for storage adapters."""
    
    @abstractmethod
    async def upload(self, local_path: str, remote_path: str, encrypt: bool = True) -> bool:
        """
        Upload file to remote storage.
        
        Args:
            local_path: Path to local file
            remote_path: Path in remote storage
            encrypt: Whether to encrypt the file
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def download(self, remote_path: str, local_path: str, decrypt: bool = True) -> bool:
        """
        Download file from remote storage.
        
        Args:
            remote_path: Path in remote storage
            local_path: Path to save locally
            decrypt: Whether to decrypt the file
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def list_files(self, prefix: str) -> list[str]:
        """
        List files in remote storage with given prefix.
        
        Args:
            prefix: Path prefix to filter files
            
        Returns:
            List of file paths
        """
        pass
    
    @abstractmethod
    async def delete(self, remote_path: str) -> bool:
        """
        Delete file from remote storage.
        
        Args:
            remote_path: Path in remote storage
            
        Returns:
            True if successful, False otherwise
        """
        pass

class LocalStorageAdapter(StorageAdapter):
    """Local filesystem storage adapter for testing and development."""
    
    def __init__(self, base_path: str = "backups"):
        """
        Initialize local storage adapter.
        
        Args:
            base_path: Base directory for backups
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Local storage adapter initialized at {self.base_path}")
    
    async def upload(self, local_path: str, remote_path: str, encrypt: bool = True) -> bool:
        """Upload file to local storage (copy)."""
        try:
            source = Path(local_path)
            destination = self.base_path / remote_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Compress the file
            if not str(destination).endswith('.gz'):
                destination = Path(str(destination) + '.gz')
            
            with open(source, 'rb') as f_in:
                with gzip.open(destination, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            logger.info(f"Uploaded {local_path} to {destination}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {e}")
            return False
    
    async def download(self, remote_path: str, local_path: str, decrypt: bool = True) -> bool:
        """Download file from local storage (copy)."""
        try:
            source = self.base_path / remote_path
            if not source.exists() and not str(source).endswith('.gz'):
                source = Path(str(source) + '.gz')
            
            destination = Path(local_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Decompress if needed
            if str(source).endswith('.gz'):
                with gzip.open(source, 'rb') as f_in:
                    with open(destination, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                shutil.copy2(source, destination)
            
            logger.info(f"Downloaded {source} to {local_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download {remote_path}: {e}")
            return False
    
    async def list_files(self, prefix: str) -> list[str]:
        """List files in local storage with given prefix."""
        try:
            prefix_path = self.base_path / prefix
            if not prefix_path.exists():
                return []
            
            files = []
            for file_path in prefix_path.rglob('*'):
                if file_path.is_file():
                    relative_path = file_path.relative_to(self.base_path)
                    files.append(str(relative_path))
            
            return sorted(files)
        except Exception as e:
            logger.error(f"Failed to list files with prefix {prefix}: {e}")
            return []
    
    async def delete(self, remote_path: str) -> bool:
        """Delete file from local storage."""
        try:
            file_path = self.base_path / remote_path
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted {file_path}")
                return True
            else:
                logger.warning(f"File not found: {file_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete {remote_path}: {e}")
            return False

class S3StorageAdapter(StorageAdapter):
    """AWS S3 storage adapter."""
    
    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
        encryption_key: Optional[str] = None,
    ):
        """
        Initialize S3 storage adapter.
        
        Args:
            bucket_name: S3 bucket name
            aws_access_key_id: AWS access key (optional, uses env vars if not provided)
            aws_secret_access_key: AWS secret key (optional, uses env vars if not provided)
            region_name: AWS region
            encryption_key: Encryption key for client-side encryption
        """
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            self.bucket_name = bucket_name
            self.encryption_key = encryption_key
            self.ClientError = ClientError
            
            # Initialize S3 client
            session_kwargs = {'region_name': region_name}
            if aws_access_key_id and aws_secret_access_key:
                session_kwargs['aws_access_key_id'] = aws_access_key_id
                session_kwargs['aws_secret_access_key'] = aws_secret_access_key
            
            self.s3_client = boto3.client('s3', **session_kwargs)
            
            # Verify bucket exists
            try:
                self.s3_client.head_bucket(Bucket=bucket_name)
                logger.info(f"S3 storage adapter initialized for bucket {bucket_name}")
            except ClientError as e:
                logger.error(f"Bucket {bucket_name} not accessible: {e}")
                raise
                
        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            raise
    
    async def upload(self, local_path: str, remote_path: str, encrypt: bool = True) -> bool:
        """Upload file to S3."""
        try:
            extra_args = {}
            if encrypt and self.encryption_key:
                extra_args['ServerSideEncryption'] = 'AES256'
            
            # Compress before upload
            compressed_path = f"{local_path}.gz"
            with open(local_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Upload compressed file
            if not remote_path.endswith('.gz'):
                remote_path = f"{remote_path}.gz"
            
            self.s3_client.upload_file(
                compressed_path,
                self.bucket_name,
                remote_path,
                ExtraArgs=extra_args
            )
            
            # Clean up compressed file
            os.remove(compressed_path)
            
            logger.info(f"Uploaded {local_path} to s3://{self.bucket_name}/{remote_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to S3: {e}")
            return False
    
    async def download(self, remote_path: str, local_path: str, decrypt: bool = True) -> bool:
        """Download file from S3."""
        try:
            # Download to temporary compressed file
            if not remote_path.endswith('.gz'):
                remote_path = f"{remote_path}.gz"
            
            compressed_path = f"{local_path}.gz"
            
            self.s3_client.download_file(
                self.bucket_name,
                remote_path,
                compressed_path
            )
            
            # Decompress
            with gzip.open(compressed_path, 'rb') as f_in:
                with open(local_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Clean up compressed file
            os.remove(compressed_path)
            
            logger.info(f"Downloaded s3://{self.bucket_name}/{remote_path} to {local_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download {remote_path} from S3: {e}")
            return False
    
    async def list_files(self, prefix: str) -> list[str]:
        """List files in S3 with given prefix."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents']]
            
            return sorted(files)
        except Exception as e:
            logger.error(f"Failed to list files with prefix {prefix} in S3: {e}")
            return []
    
    async def delete(self, remote_path: str) -> bool:
        """Delete file from S3."""
        try:
            if not remote_path.endswith('.gz'):
                remote_path = f"{remote_path}.gz"
            
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=remote_path
            )
            logger.info(f"Deleted s3://{self.bucket_name}/{remote_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {remote_path} from S3: {e}")
            return False
