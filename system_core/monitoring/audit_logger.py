"""
Audit logging system for compliance and security tracking.

Validates: Requirements 39.1, 39.2, 39.3, 39.4, 39.8
"""

import hmac
import hashlib
import json
import logging
import socket
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from uuid import UUID
from logging.handlers import RotatingFileHandler, SysLogHandler

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.database.models import AuditLog
from system_core.monitoring.logger import get_logger

# Audit logger instance
audit_file_logger = None
syslog_handler = None

class AuditLogger:
    """
    Audit logging system with tamper-proof signatures and SIEM integration.
    
    Features:
    - Separate append-only audit log file
    - HMAC-SHA256 signatures for tamper-proof logging
    - Real-time SIEM integration via syslog
    - Database storage for querying
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        secret_key: Optional[str] = None,
        config_path: str = "config/audit_config.yaml",
        audit_log_path: Optional[str] = None,
        max_bytes: Optional[int] = None,
        backup_count: Optional[int] = None,
        syslog_enabled: Optional[bool] = None,
        syslog_address: Optional[tuple] = None
    ):
        """
        Initialize audit logger.
        
        Args:
            db_session: Database session for storing audit logs
            secret_key: Secret key for HMAC-SHA256 signatures (overrides config)
            config_path: Path to audit configuration YAML file
            audit_log_path: Path to audit log file (overrides config)
            max_bytes: Maximum size of each log file (overrides config)
            backup_count: Number of backup files to keep (overrides config)
            syslog_enabled: Enable SIEM integration via syslog (overrides config)
            syslog_address: Syslog server address (host, port) (overrides config)
        """
        self.db_session = db_session
        self.logger = get_logger(__name__)
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Override with parameters if provided
        if secret_key:
            self.secret_key = secret_key.encode('utf-8')
        else:
            self.secret_key = self.config.get('secret_key', 'default_secret_key').encode('utf-8')
        
        audit_log_config = self.config.get('audit_log', {})
        self.audit_log_path = audit_log_path or audit_log_config.get('path', 'logs/audit.log')
        self.max_bytes = max_bytes or audit_log_config.get('max_bytes', 104857600)
        self.backup_count = backup_count or audit_log_config.get('backup_count', 365)
        
        siem_config = self.config.get('siem', {})
        self.syslog_enabled = syslog_enabled if syslog_enabled is not None else siem_config.get('enabled', False)
        self.syslog_address = syslog_address or tuple(siem_config.get('address', ['localhost', 514]))
        
        # Set up file logger for audit logs
        self._setup_file_logger(self.audit_log_path, self.max_bytes, self.backup_count)
        
        # Set up syslog handler for SIEM integration
        if self.syslog_enabled:
            self._setup_syslog_handler(self.syslog_address)
    
    def _load_config(self, config_path: str) -> dict[str, Any]:
        """Load audit configuration from YAML file."""
        try:
            config_file = Path(config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                    self.logger.info("audit_config_loaded", path=config_path)
                    return config
            else:
                self.logger.warning("audit_config_not_found", path=config_path)
                return {}
        except Exception as e:
            self.logger.error("failed_to_load_audit_config", error=str(e), path=config_path)
            return {}
    
    def _setup_file_logger(
        self,
        audit_log_path: str,
        max_bytes: int,
        backup_count: int
    ) -> None:
        """Set up rotating file handler for audit logs."""
        global audit_file_logger
        
        # Create logs directory if it doesn't exist
        log_dir = Path(audit_log_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create dedicated audit logger
        audit_file_logger = logging.getLogger("audit")
        audit_file_logger.setLevel(logging.INFO)
        audit_file_logger.propagate = False
        
        # Create rotating file handler with append-only mode
        file_handler = RotatingFileHandler(
            filename=audit_log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            mode='a'  # Append-only mode
        )
        
        # JSON format for structured audit logs
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        
        audit_file_logger.addHandler(file_handler)
    
    def _setup_syslog_handler(self, syslog_address: tuple) -> None:
        """Set up syslog handler for SIEM integration."""
        global syslog_handler
        
        try:
            # Determine socket type based on protocol
            siem_config = self.config.get('siem', {})
            protocol = siem_config.get('protocol', 'UDP')
            
            if protocol.upper() == 'TCP':
                socktype = socket.SOCK_STREAM
            else:
                socktype = socket.SOCK_DGRAM
            
            syslog_handler = SysLogHandler(
                address=syslog_address,
                facility=SysLogHandler.LOG_LOCAL0,
                socktype=socktype
            )
            
            # Format for syslog
            formatter = logging.Formatter(
                'OpenFi-Audit: %(message)s'
            )
            syslog_handler.setFormatter(formatter)
            
            audit_file_logger.addHandler(syslog_handler)
            self.logger.info(
                "syslog_handler_configured",
                address=syslog_address,
                protocol=protocol
            )
        except Exception as e:
            self.logger.error(
                "failed_to_setup_syslog",
                error=str(e),
                address=syslog_address
            )
    
    def _generate_signature(self, audit_data: dict[str, Any]) -> str:
        """
        Generate HMAC-SHA256 signature for audit log entry.
        
        Args:
            audit_data: Audit log data dictionary
            
        Returns:
            str: Hex-encoded HMAC-SHA256 signature
        """
        # Create canonical string from audit data
        canonical_parts = [
            str(audit_data.get('timestamp', '')),
            str(audit_data.get('user_id', '')),
            str(audit_data.get('action', '')),
            str(audit_data.get('resource_type', '')),
            str(audit_data.get('resource_id', '')),
            json.dumps(audit_data.get('old_value', {}), sort_keys=True),
            json.dumps(audit_data.get('new_value', {}), sort_keys=True),
            str(audit_data.get('ip_address', '')),
            str(audit_data.get('user_agent', ''))
        ]
        canonical_string = '|'.join(canonical_parts)
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.secret_key,
            canonical_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def log_audit_event(
        self,
        action: str,
        resource_type: str,
        user_id: Optional[UUID] = None,
        resource_id: Optional[UUID] = None,
        old_value: Optional[dict[str, Any]] = None,
        new_value: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """
        Log an audit event with tamper-proof signature.
        
        Args:
            action: Action performed (e.g., "user_login", "config_change", "trade_executed")
            resource_type: Type of resource (e.g., "user", "ea_profile", "trade", "config")
            user_id: User ID performing the action
            resource_id: ID of the resource being modified
            old_value: Previous value (for updates)
            new_value: New value (for creates/updates)
            ip_address: IP address of the client
            user_agent: User agent string
            
        Returns:
            AuditLog: Created audit log entry
            
        Validates: Requirements 39.1, 39.2, 39.3, 39.4
        """
        timestamp = datetime.utcnow()
        
        # Prepare audit data
        audit_data = {
            'timestamp': timestamp.isoformat(),
            'user_id': str(user_id) if user_id else None,
            'action': action,
            'resource_type': resource_type,
            'resource_id': str(resource_id) if resource_id else None,
            'old_value': old_value or {},
            'new_value': new_value or {},
            'ip_address': ip_address,
            'user_agent': user_agent
        }
        
        # Generate tamper-proof signature
        signature = self._generate_signature(audit_data)
        audit_data['signature'] = signature
        
        # Log to file (append-only)
        if audit_file_logger:
            audit_file_logger.info(json.dumps(audit_data))
        
        # Create database record
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
            signature=signature
        )
        
        try:
            self.db_session.add(audit_log)
            self.db_session.commit()
            
            self.logger.info(
                "audit_event_logged",
                action=action,
                resource_type=resource_type,
                user_id=str(user_id) if user_id else None,
                resource_id=str(resource_id) if resource_id else None
            )
        except Exception as e:
            self.db_session.rollback()
            self.logger.error(
                "failed_to_store_audit_log",
                error=str(e),
                action=action,
                resource_type=resource_type
            )
            raise
        
        return audit_log
    
    def verify_signature(self, audit_log: AuditLog) -> bool:
        """
        Verify the HMAC-SHA256 signature of an audit log entry.
        
        Args:
            audit_log: Audit log entry to verify
            
        Returns:
            bool: True if signature is valid, False otherwise
        """
        audit_data = {
            'timestamp': audit_log.created_at.isoformat(),
            'user_id': str(audit_log.user_id) if audit_log.user_id else None,
            'action': audit_log.action,
            'resource_type': audit_log.resource_type,
            'resource_id': str(audit_log.resource_id) if audit_log.resource_id else None,
            'old_value': audit_log.old_value or {},
            'new_value': audit_log.new_value or {},
            'ip_address': audit_log.ip_address,
            'user_agent': audit_log.user_agent
        }
        
        expected_signature = self._generate_signature(audit_data)
        return hmac.compare_digest(expected_signature, audit_log.signature or '')

# Convenience functions for common audit events

def log_user_authentication(
    audit_logger: AuditLogger,
    user_id: UUID,
    success: bool,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """Log user authentication attempt."""
    action = "user_login_success" if success else "user_login_failed"
    return audit_logger.log_audit_event(
        action=action,
        resource_type="user",
        user_id=user_id,
        resource_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent
    )

def log_config_change(
    audit_logger: AuditLogger,
    config_file: str,
    old_value: dict[str, Any],
    new_value: dict[str, Any],
    user_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """Log configuration file change."""
    return audit_logger.log_audit_event(
        action="config_change",
        resource_type="config",
        user_id=user_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=user_agent
    )

def log_trade_execution(
    audit_logger: AuditLogger,
    trade_id: UUID,
    trade_data: dict[str, Any],
    user_id: Optional[UUID] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """Log trade execution."""
    return audit_logger.log_audit_event(
        action="trade_executed",
        resource_type="trade",
        user_id=user_id,
        resource_id=trade_id,
        new_value=trade_data,
        ip_address=ip_address
    )

def log_ea_profile_modification(
    audit_logger: AuditLogger,
    ea_profile_id: UUID,
    old_value: dict[str, Any],
    new_value: dict[str, Any],
    user_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """Log EA profile modification."""
    return audit_logger.log_audit_event(
        action="ea_profile_modified",
        resource_type="ea_profile",
        user_id=user_id,
        resource_id=ea_profile_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        user_agent=user_agent
    )

def log_manual_override(
    audit_logger: AuditLogger,
    override_type: str,
    resource_id: UUID,
    override_data: dict[str, Any],
    user_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditLog:
    """Log manual override action."""
    return audit_logger.log_audit_event(
        action=f"manual_override_{override_type}",
        resource_type=override_type,
        user_id=user_id,
        resource_id=resource_id,
        new_value=override_data,
        ip_address=ip_address,
        user_agent=user_agent
    )

