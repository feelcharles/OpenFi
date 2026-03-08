"""
Security event logging.

Logs security-related events for audit and monitoring.

Requirements: 42.10
"""

from typing import Optional, Any
from datetime import datetime
from enum import Enum

from system_core.config import get_logger

logger = get_logger(__name__)

class SecurityEventType(str, Enum):
    """Security event types."""
    
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    
    # Authorization events
    ACCESS_DENIED = "access_denied"
    PERMISSION_DENIED = "permission_denied"
    ROLE_VIOLATION = "role_violation"
    
    # Suspicious activities
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    COMMAND_INJECTION_ATTEMPT = "command_injection_attempt"
    XSS_ATTEMPT = "xss_attempt"
    INVALID_INPUT = "invalid_input"
    REQUEST_TOO_LARGE = "request_too_large"
    
    # Data access events
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"
    ENCRYPTION_FAILED = "encryption_failed"
    DECRYPTION_FAILED = "decryption_failed"
    
    # Configuration events
    CONFIG_CHANGED = "config_changed"
    SECRET_ACCESSED = "secret_accessed"
    
    # System events
    SECURITY_SCAN_FAILED = "security_scan_failed"
    VULNERABILITY_DETECTED = "vulnerability_detected"

class SecurityLogger:
    """
    Security event logger.
    
    Requirements: 42.10
    """
    
    def __init__(self):
        """Initialize security logger."""
        self.logger = get_logger("security")
    
    def log_event(
        self,
        event_type: SecurityEventType,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        severity: str = "info"
    ) -> None:
        """
        Log security event.
        
        Args:
            event_type: Type of security event
            user_id: User identifier (if applicable)
            ip_address: IP address of request
            details: Additional event details
            severity: Log severity (info, warning, error)
        """
        event_data = {
            "event_type": event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details or {}
        }
        
        # Log with appropriate severity
        if severity == "error":
            self.logger.error("security_event", **event_data)
        elif severity == "warning":
            self.logger.warning("security_event", **event_data)
        else:
            self.logger.info("security_event", **event_data)
    
    def log_authentication_success(
        self,
        user_id: str,
        ip_address: str,
        method: str = "password"
    ) -> None:
        """Log successful authentication."""
        self.log_event(
            SecurityEventType.LOGIN_SUCCESS,
            user_id=user_id,
            ip_address=ip_address,
            details={"method": method},
            severity="info"
        )
    
    def log_authentication_failure(
        self,
        username: str,
        ip_address: str,
        reason: str
    ) -> None:
        """Log failed authentication attempt."""
        self.log_event(
            SecurityEventType.LOGIN_FAILED,
            user_id=username,
            ip_address=ip_address,
            details={"reason": reason},
            severity="warning"
        )
    
    def log_authorization_failure(
        self,
        user_id: str,
        resource: str,
        action: str,
        ip_address: Optional[str] = None
    ) -> None:
        """Log authorization failure."""
        self.log_event(
            SecurityEventType.ACCESS_DENIED,
            user_id=user_id,
            ip_address=ip_address,
            details={
                "resource": resource,
                "action": action
            },
            severity="warning"
        )
    
    def log_suspicious_activity(
        self,
        event_type: SecurityEventType,
        ip_address: str,
        details: dict[str, Any],
        user_id: Optional[str] = None
    ) -> None:
        """Log suspicious activity."""
        self.log_event(
            event_type,
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            severity="error"
        )
    
    def log_rate_limit_exceeded(
        self,
        user_id: Optional[str],
        ip_address: str,
        endpoint: str,
        limit: int
    ) -> None:
        """Log rate limit exceeded."""
        self.log_event(
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            user_id=user_id,
            ip_address=ip_address,
            details={
                "endpoint": endpoint,
                "limit": limit
            },
            severity="warning"
        )
    
    def log_injection_attempt(
        self,
        attack_type: str,
        ip_address: str,
        payload_preview: str,
        user_id: Optional[str] = None
    ) -> None:
        """Log injection attack attempt."""
        event_type_map = {
            "sql": SecurityEventType.SQL_INJECTION_ATTEMPT,
            "command": SecurityEventType.COMMAND_INJECTION_ATTEMPT,
            "xss": SecurityEventType.XSS_ATTEMPT
        }
        
        event_type = event_type_map.get(attack_type, SecurityEventType.INVALID_INPUT)
        
        self.log_event(
            event_type,
            user_id=user_id,
            ip_address=ip_address,
            details={
                "attack_type": attack_type,
                "payload_preview": payload_preview[:100]  # Limit size
            },
            severity="error"
        )
    
    def log_sensitive_data_access(
        self,
        user_id: str,
        resource: str,
        action: str,
        ip_address: Optional[str] = None
    ) -> None:
        """Log access to sensitive data."""
        self.log_event(
            SecurityEventType.SENSITIVE_DATA_ACCESS,
            user_id=user_id,
            ip_address=ip_address,
            details={
                "resource": resource,
                "action": action
            },
            severity="info"
        )
    
    def log_config_change(
        self,
        user_id: str,
        config_file: str,
        changes: dict[str, Any],
        ip_address: Optional[str] = None
    ) -> None:
        """Log configuration change."""
        self.log_event(
            SecurityEventType.CONFIG_CHANGED,
            user_id=user_id,
            ip_address=ip_address,
            details={
                "config_file": config_file,
                "changes": changes
            },
            severity="info"
        )

# Global security logger instance
_security_logger: Optional[SecurityLogger] = None

def get_security_logger() -> SecurityLogger:
    """Get global security logger instance."""
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger

# Convenience functions
def log_security_event(
    event_type: SecurityEventType,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    severity: str = "info"
) -> None:
    """Log security event (convenience function)."""
    logger = get_security_logger()
    logger.log_event(event_type, user_id, ip_address, details, severity)
