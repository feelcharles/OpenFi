"""
Secure Configuration Manager

Provides secure access control for sensitive configuration files and fields.
Prevents unauthorized access to API keys, passwords, and other credentials.

Requirements: 42.1, 42.2, 42.3, 42.4
"""

import logging
from typing import Any, Optional
from enum import Enum
from pathlib import Path

from system_core.config.global_config import get_global_config_manager
from system_core.core.exceptions import ConfigurationError
from system_core.security.encryption import encrypt_dict, decrypt_dict

logger = logging.getLogger(__name__)

class AccessLevel(str, Enum):
    """Access level for configuration access"""
    SYSTEM = "system"  # Full access (internal system components)
    USER = "user"      # User-level access (web API, CLI)
    AI = "ai"          # AI/LLM access (restricted)
    AGENT = "agent"    # Agent access (most restricted)

class RequesterContext:
    """Context information about the configuration requester"""
    
    def __init__(
        self,
        requester_type: str,
        requester_id: Optional[str] = None,
        access_level: AccessLevel = AccessLevel.AGENT,
        user_id: Optional[str] = None,
        permissions: Optional[set[str]] = None
    ):
        """
        Initialize requester context.
        
        Args:
            requester_type: Type of requester (e.g., "llm_client", "agent", "web_api")
            requester_id: Unique identifier of requester
            access_level: Access level
            user_id: Associated user ID (if applicable)
            permissions: Set of granted permissions
        """
        self.requester_type = requester_type
        self.requester_id = requester_id
        self.access_level = access_level
        self.user_id = user_id
        self.permissions = permissions or set()

class SecureConfigManager:
    """
    Secure Configuration Manager with access control.
    
    Protects sensitive configuration files and fields from unauthorized access,
    especially from AI/LLM engines and agents.
    """
    
    # Sensitive configuration files (require elevated access)
    SENSITIVE_CONFIGS = {
        'accounts.yaml',
        'security_config.yaml',
        'fetch_sources.yaml',  # Contains API keys
        'push_config.yaml',    # Contains bot tokens
        'external_tools.yaml', # Contains API credentials
    }
    
    # Sensitive field patterns (will be filtered based on access level)
    SENSITIVE_FIELD_PATTERNS = {
        'password',
        'api_key',
        'secret',
        'token',
        'credentials',
        'private_key',
        'access_token',
        'refresh_token',
        'webhook_url',
        'api_secret',
    }
    
    # Access level permissions
    ACCESS_PERMISSIONS = {
        AccessLevel.SYSTEM: {
            'read_all_configs',
            'read_sensitive_fields',
            'write_configs',
        },
        AccessLevel.USER: {
            'read_all_configs',
            'read_sensitive_fields',  # User can see their own credentials
            'write_configs',
        },
        AccessLevel.AI: {
            'read_public_configs',
            # AI cannot read sensitive fields
        },
        AccessLevel.AGENT: {
            'read_public_configs',
            'read_agent_configs',
            # Agent cannot read sensitive fields
        },
    }
    
    def __init__(self):
        """Initialize secure configuration manager."""
        self.config_manager = get_global_config_manager()
        self._access_log: list[dict[str, Any]] = []
    
    def get_config(
        self,
        filename: str,
        context: RequesterContext
    ) -> Optional[dict[str, Any]]:
        """
        Get configuration with access control.
        
        Args:
            filename: Configuration file name
            context: Requester context
        
        Returns:
            Configuration dictionary (filtered based on access level)
        
        Raises:
            PermissionError: If access is denied
        """
        # Log access attempt
        self._log_access(filename, context, "read")
        
        # Check if file is sensitive
        if filename in self.SENSITIVE_CONFIGS:
            if not self._is_authorized_for_sensitive(context):
                logger.warning(
                    f"Access denied to sensitive config {filename} "
                    f"for {context.requester_type} (level: {context.access_level})"
                )
                raise PermissionError(
                    f"Access denied: {context.requester_type} cannot access {filename}"
                )
        
        # Load configuration
        config = self.config_manager.get_config(filename)
        
        if config is None:
            return None
        
        # Filter sensitive fields based on access level
        filtered_config = self._filter_sensitive_fields(config, context)
        
        return filtered_config
    
    def get_config_safe(
        self,
        filename: str,
        context: RequesterContext,
        default: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Get configuration safely (returns default instead of raising exception).
        
        Args:
            filename: Configuration file name
            context: Requester context
            default: Default value if access denied or config not found
        
        Returns:
            Configuration dictionary or default
        """
        try:
            config = self.get_config(filename, context)
            return config if config is not None else (default or {})
        except PermissionError:
            logger.info(
                f"Access denied to {filename} for {context.requester_type}, "
                f"returning default"
            )
            return default or {}
    
    def _is_authorized_for_sensitive(self, context: RequesterContext) -> bool:
        """
        Check if requester is authorized to access sensitive configs.
        
        Args:
            context: Requester context
        
        Returns:
            True if authorized, False otherwise
        """
        # System and User levels can access sensitive configs
        if context.access_level in [AccessLevel.SYSTEM, AccessLevel.USER]:
            return True
        
        # AI and Agent levels cannot access sensitive configs
        return False
    
    def _filter_sensitive_fields(
        self,
        config: dict[str, Any],
        context: RequesterContext
    ) -> dict[str, Any]:
        """
        Filter sensitive fields from configuration based on access level.
        
        Args:
            config: Configuration dictionary
            context: Requester context
        
        Returns:
            Filtered configuration
        """
        # System level gets everything
        if context.access_level == AccessLevel.SYSTEM:
            return config
        
        # User level gets everything (they own the credentials)
        if context.access_level == AccessLevel.USER:
            return config
        
        # AI and Agent levels get filtered config
        return self._recursive_filter(config, context)
    
    def _recursive_filter(
        self,
        data: Any,
        context: RequesterContext
    ) -> Any:
        """
        Recursively filter sensitive fields from nested structures.
        
        Args:
            data: Data to filter (dict, list, or primitive)
            context: Requester context
        
        Returns:
            Filtered data
        """
        if isinstance(data, dict):
            filtered = {}
            for key, value in data.items():
                # Check if key is sensitive
                if self._is_sensitive_field(key):
                    # Replace with placeholder
                    filtered[key] = "[REDACTED]"
                    logger.debug(
                        f"Filtered sensitive field '{key}' for "
                        f"{context.requester_type}"
                    )
                else:
                    # Recursively filter nested structures
                    filtered[key] = self._recursive_filter(value, context)
            return filtered
        
        elif isinstance(data, list):
            return [self._recursive_filter(item, context) for item in data]
        
        else:
            # Primitive value, return as-is
            return data
    
    def _is_sensitive_field(self, field_name: str) -> bool:
        """
        Check if field name indicates sensitive data.
        
        Args:
            field_name: Field name to check
        
        Returns:
            True if sensitive, False otherwise
        """
        field_lower = field_name.lower()
        
        # Check exact matches
        if field_lower in self.SENSITIVE_FIELD_PATTERNS:
            return True
        
        # Check if any pattern is contained in field name
        for pattern in self.SENSITIVE_FIELD_PATTERNS:
            if pattern in field_lower:
                return True
        
        return False
    
    def _log_access(
        self,
        filename: str,
        context: RequesterContext,
        operation: str
    ) -> None:
        """
        Log configuration access attempt.
        
        Args:
            filename: Configuration file name
            context: Requester context
            operation: Operation type (read, write)
        """
        from datetime import datetime
        
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'filename': filename,
            'operation': operation,
            'requester_type': context.requester_type,
            'requester_id': context.requester_id,
            'access_level': context.access_level.value,
            'user_id': context.user_id,
        }
        
        self._access_log.append(log_entry)
        
        # Keep only last 1000 entries
        if len(self._access_log) > 1000:
            self._access_log = self._access_log[-1000:]
        
        # Log to file for audit
        logger.info(
            "config_access",
            extra=log_entry
        )
    
    def get_access_log(
        self,
        limit: int = 100,
        requester_type: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Get configuration access log.
        
        Args:
            limit: Maximum number of entries to return
            requester_type: Filter by requester type (optional)
        
        Returns:
            List of access log entries
        """
        log = self._access_log
        
        if requester_type:
            log = [
                entry for entry in log
                if entry['requester_type'] == requester_type
            ]
        
        return log[-limit:]

# Global secure config manager instance
_secure_config_manager: Optional[SecureConfigManager] = None

def get_secure_config_manager() -> SecureConfigManager:
    """
    Get global secure configuration manager instance.
    
    Returns:
        Global secure config manager
    """
    global _secure_config_manager
    if _secure_config_manager is None:
        _secure_config_manager = SecureConfigManager()
    return _secure_config_manager

# Convenience functions for common access patterns
def get_config_for_system(filename: str) -> Optional[dict[str, Any]]:
    """Get configuration with system-level access (full access)."""
    context = RequesterContext(
        requester_type="system",
        access_level=AccessLevel.SYSTEM
    )
    manager = get_secure_config_manager()
    return manager.get_config(filename, context)

def get_config_for_ai(filename: str) -> dict[str, Any]:
    """Get configuration with AI-level access (sensitive fields filtered)."""
    context = RequesterContext(
        requester_type="ai_engine",
        access_level=AccessLevel.AI
    )
    manager = get_secure_config_manager()
    return manager.get_config_safe(filename, context, default={})

def get_config_for_agent(
    filename: str,
    agent_id: str,
    user_id: Optional[str] = None
) -> dict[str, Any]:
    """Get configuration with agent-level access (most restricted)."""
    context = RequesterContext(
        requester_type="agent",
        requester_id=agent_id,
        access_level=AccessLevel.AGENT,
        user_id=user_id
    )
    manager = get_secure_config_manager()
    return manager.get_config_safe(filename, context, default={})

__all__ = [
    'SecureConfigManager',
    'RequesterContext',
    'AccessLevel',
    'get_secure_config_manager',
    'get_config_for_system',
    'get_config_for_ai',
    'get_config_for_agent',
]
