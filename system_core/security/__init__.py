"""
Security module for OpenFi Lite.

Provides input validation, sanitization, encryption, and security utilities.
"""

from .input_validation import (
    sanitize_string,
    sanitize_sql_input,
    sanitize_command_input,
    sanitize_html,
    validate_request_size,
    RequestSizeLimitMiddleware
)
from .encryption import (
    encrypt_data,
    decrypt_data,
    hash_sensitive_data,
    SecretManager
)
from .security_headers import SecurityHeadersMiddleware
from .security_logger import (
    SecurityLogger,
    SecurityEventType,
    get_security_logger,
    log_security_event
)

__all__ = [
    "sanitize_string",
    "sanitize_sql_input",
    "sanitize_command_input",
    "sanitize_html",
    "validate_request_size",
    "RequestSizeLimitMiddleware",
    "encrypt_data",
    "decrypt_data",
    "hash_sensitive_data",
    "SecretManager",
    "SecurityHeadersMiddleware",
    "SecurityLogger",
    "SecurityEventType",
    "get_security_logger",
    "log_security_event",
]
