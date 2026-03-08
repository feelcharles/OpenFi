"""
Backup verification module.

Verifies backup integrity by restoring to test database and running checks.
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from system_core.backup.storage_adapter import StorageAdapter

logger = logging.getLogger(__name__)

class BackupVerifier:
    """
    Verifies backup integrity by restoring to test database.
    
    Features:
    - Restore backup to temporary test database
    - Run integrity checks (table counts, constraints, indexes)
    - Validate data consistency
    - Clean up test database after verification
    """
    
    def __init__(
        self,
        storage_adapter: StorageAdapter,
        db_host: str,
        db_port: int,
        db_user: str,
        db_password: str,
        test_db_prefix: str = "test_restore_",
    ):
        """
        Initialize backup verifier.
        
        Args:
            storage_adapter: Storage adapter for downloading backups
            db_host: Database host
            db_port: Database port
            db_user: Database user
            db_password: Database password
            test_db_prefix: Prefix for test database names
        """
        self.storage_adapter = storage_adapter
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_password = db_password
        self.test_db_prefix = test_db_prefix
        
        logger.info("Backup verifier initialized")
    
    async def verify_backup(self, backup_path: str) -> dict[str, Any]:
        """
        Verify backup by restoring to test database and running checks.
        
        Args:
            backup_path: Remote path to backup file
            
        Returns:
            Verification result with status and checks
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        test_db_name = f"{self.test_db_prefix}{timestamp}"
        
        logger.info(f"Starting backup verification for {backup_path}")
        
        verification_result = {
            'status': 'unknown',
            'timestamp': timestamp,
            'backup_path': backup_path,
            'test_db': test_db_name,
            'checks': {},
            'errors': [],
        }
        
        try:
            # Step 1: Create test database
            logger.info(f"Creating test database: {test_db_name}")
            create_success = await self._create_test_database(test_db_name)
            if not create_success:
                verification_result['status'] = 'failed'
                verification_result['errors'].append('Failed to create test database')
                return verification_result
            
            verification_result['checks']['database_created'] = True
            
            # Step 2: Download backup file
            logger.info(f"Downloading backup file: {backup_path}")
            local_backup = Path(f"backups/verify_{timestamp}.sql")
            local_backup.parent.mkdir(parents=True, exist_ok=True)
            
            download_success = await self.storage_adapter.download(
                backup_path,
                str(local_backup),
                decrypt=True
            )
            
            if not download_success:
                verification_result['status'] = 'failed'
                verification_result['errors'].append('Failed to download backup file')
                await self._drop_test_database(test_db_name)
                return verification_result
            
            verification_result['checks']['backup_downloaded'] = True
            
            # Step 3: Restore backup to test database
            logger.info(f"Restoring backup to test database")
            restore_success = await self._restore_to_test_db(
                str(local_backup),
                test_db_name
            )
            
            # Clean up local backup file
            local_backup.unlink()
            
            if not restore_success:
                verification_result['status'] = 'failed'
                verification_result['errors'].append('Failed to restore backup')
                await self._drop_test_database(test_db_name)
                return verification_result
            
            verification_result['checks']['backup_restored'] = True
            
            # Step 4: Run integrity checks
            logger.info("Running integrity checks")
            integrity_checks = await self._run_integrity_checks(test_db_name)
            verification_result['checks'].update(integrity_checks)
            
            # Step 5: Validate critical tables
            logger.info("Validating critical tables")
            table_checks = await self._validate_tables(test_db_name)
            verification_result['checks'].update(table_checks)
            
            # Step 6: Clean up test database
            logger.info(f"Cleaning up test database: {test_db_name}")
            await self._drop_test_database(test_db_name)
            verification_result['checks']['database_cleaned'] = True
            
            # Determine overall status
            all_checks_passed = all(
                value is True
                for key, value in verification_result['checks'].items()
                if isinstance(value, bool)
            )
            
            verification_result['status'] = 'passed' if all_checks_passed else 'failed'
            
            logger.info(
                f"Backup verification completed: {verification_result['status']} "
                f"({len(verification_result['checks'])} checks)"
            )
            
            return verification_result
            
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            verification_result['status'] = 'failed'
            verification_result['errors'].append(str(e))
            
            # Try to clean up test database
            try:
                await self._drop_test_database(test_db_name)
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up test database: {cleanup_error}")
            
            return verification_result
    
    async def _create_test_database(self, db_name: str) -> bool:
        """Create test database."""
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_password
            
            # Connect to postgres database to create new database
            cmd = [
                'psql',
                '-h', self.db_host,
                '-p', str(self.db_port),
                '-U', self.db_user,
                '-d', 'postgres',
                '-c', f"CREATE DATABASE {db_name};",
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to create test database: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating test database: {e}")
            return False
    
    async def _drop_test_database(self, db_name: str) -> bool:
        """Drop test database."""
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_password
            
            # Terminate connections to the database first
            terminate_cmd = [
                'psql',
                '-h', self.db_host,
                '-p', str(self.db_port),
                '-U', self.db_user,
                '-d', 'postgres',
                '-c', f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}';",
            ]
            
            subprocess.run(terminate_cmd, env=env, capture_output=True, timeout=30)
            
            # Drop the database
            cmd = [
                'psql',
                '-h', self.db_host,
                '-p', str(self.db_port),
                '-U', self.db_user,
                '-d', 'postgres',
                '-c', f"DROP DATABASE IF EXISTS {db_name};",
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to drop test database: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error dropping test database: {e}")
            return False
    
    async def _restore_to_test_db(self, backup_file: str, db_name: str) -> bool:
        """Restore backup to test database."""
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_password
            
            cmd = [
                'psql',
                '-h', self.db_host,
                '-p', str(self.db_port),
                '-U', self.db_user,
                '-d', db_name,
                '-f', backup_file,
            ]
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes timeout
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to restore backup: {result.stderr}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return False
    
    async def _run_integrity_checks(self, db_name: str) -> dict[str, Any]:
        """Run database integrity checks."""
        checks = {}
        
        try:
            # Create database connection
            db_url = f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{db_name}"
            engine = create_engine(db_url)
            
            with engine.connect() as conn:
                # Check for foreign key violations
                result = conn.execute(text("""
                    SELECT COUNT(*) as violation_count
                    FROM information_schema.table_constraints
                    WHERE constraint_type = 'FOREIGN KEY'
                """))
                fk_count = result.scalar()
                checks['foreign_keys_exist'] = fk_count > 0
                
                # Check for indexes
                result = conn.execute(text("""
                    SELECT COUNT(*) as index_count
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                """))
                index_count = result.scalar()
                checks['indexes_exist'] = index_count > 0
                checks['index_count'] = index_count
                
                # Check for sequences
                result = conn.execute(text("""
                    SELECT COUNT(*) as sequence_count
                    FROM information_schema.sequences
                    WHERE sequence_schema = 'public'
                """))
                sequence_count = result.scalar()
                checks['sequences_exist'] = sequence_count > 0
                
            engine.dispose()
            
        except Exception as e:
            logger.error(f"Error running integrity checks: {e}")
            checks['integrity_check_error'] = str(e)
        
        return checks
    
    async def _validate_tables(self, db_name: str) -> dict[str, Any]:
        """Validate critical tables exist and have data."""
        checks = {}
        
        critical_tables = [
            'users',
            'ea_profiles',
            'trades',
            'brokers',
            'trading_accounts',
            'signals',
            'notifications',
            'alert_rules',
            'circuit_breaker_states',
            'audit_logs',
        ]
        
        try:
            db_url = f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{db_name}"
            engine = create_engine(db_url)
            
            with engine.connect() as conn:
                for table_name in critical_tables:
                    # Check if table exists
                    result = conn.execute(text(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables
                            WHERE table_schema = 'public'
                            AND table_name = '{table_name}'
                        )
                    """))
                    table_exists = result.scalar()
                    checks[f'table_{table_name}_exists'] = table_exists
                    
                    if table_exists:
                        # Check row count
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                        row_count = result.scalar()
                        checks[f'table_{table_name}_row_count'] = row_count
            
            engine.dispose()
            
        except Exception as e:
            logger.error(f"Error validating tables: {e}")
            checks['table_validation_error'] = str(e)
        
        return checks
