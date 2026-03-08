"""
Input validation and sanitization utilities.

Provides functions to sanitize user inputs and prevent injection attacks.

Requirements: 42.1, 42.2
"""

import re
import html
from typing import Any, Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from system_core.config import get_logger

logger = get_logger(__name__)

# Maximum request size in bytes (10 MB)
MAX_REQUEST_SIZE = 10 * 1024 * 1024

# Dangerous patterns for SQL injection
SQL_INJECTION_PATTERNS = [
    r"(\bUNION\b.*\bSELECT\b)",
    r"(\bSELECT\b.*\bFROM\b)",
    r"(\bINSERT\b.*\bINTO\b)",
    r"(\bUPDATE\b.*\bSET\b)",
    r"(\bDELETE\b.*\bFROM\b)",
    r"(\bDROP\b.*\bTABLE\b)",
    r"(--|\#|\/\*|\*\/)",  # SQL comments
    r"(\bOR\b.*=.*)",
    r"(\bAND\b.*=.*)",
    r"(;.*\b(SELECT|INSERT|UPDATE|DELETE|DROP)\b)",
]

# Dangerous patterns for command injection
COMMAND_INJECTION_PATTERNS = [
    r"[;&|`$()]",  # Shell metacharacters
    r"\$\{.*\}",  # Variable expansion
    r"\$\(.*\)",  # Command substitution
    r"`.*`",  # Backtick command substitution
    r">\s*\/",  # Redirect to file
    r"<\s*\/",  # Redirect from file
]

# XSS patterns
XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",  # Event handlers like onclick=
    r"<iframe[^>]*>",
    r"<object[^>]*>",
    r"<embed[^>]*>",
]

def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize a string by removing dangerous characters.
    
    Args:
        value: Input string to sanitize
        max_length: Maximum allowed length
    
    Returns:
        Sanitized string
    
    Raises:
        ValueError: If input contains dangerous patterns
    """
    if not isinstance(value, str):
        raise ValueError(f"Expected string, got {type(value)}")
    
    # Check length
    if max_length and len(value) > max_length:
        raise ValueError(f"String exceeds maximum length of {max_length}")
    
    # Strip leading/trailing whitespace
    value = value.strip()
    
    # Check for null bytes
    if '\x00' in value:
        raise ValueError("String contains null bytes")
    
    return value

def sanitize_sql_input(value: str) -> str:
    """
    Sanitize input to prevent SQL injection.
    
    Note: This is a defense-in-depth measure. Always use parameterized queries.
    
    Args:
        value: Input string to sanitize
    
    Returns:
        Sanitized string
    
    Raises:
        ValueError: If input contains SQL injection patterns
    """
    value = sanitize_string(value)
    
    # Check for SQL injection patterns
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning(
                "sql_injection_attempt_detected",
                pattern=pattern,
                value_preview=value[:100]
            )
            raise ValueError("Input contains potentially dangerous SQL patterns")
    
    return value

def sanitize_command_input(value: str) -> str:
    """
    Sanitize input to prevent command injection.
    
    Args:
        value: Input string to sanitize
    
    Returns:
        Sanitized string
    
    Raises:
        ValueError: If input contains command injection patterns
    """
    value = sanitize_string(value)
    
    # Check for command injection patterns
    for pattern in COMMAND_INJECTION_PATTERNS:
        if re.search(pattern, value):
            logger.warning(
                "command_injection_attempt_detected",
                pattern=pattern,
                value_preview=value[:100]
            )
            raise ValueError("Input contains potentially dangerous command patterns")
    
    return value

def sanitize_html(value: str) -> str:
    """
    Sanitize HTML input to prevent XSS attacks.
    
    Args:
        value: Input string to sanitize
    
    Returns:
        HTML-escaped string
    
    Raises:
        ValueError: If input contains XSS patterns
    """
    value = sanitize_string(value)
    
    # Check for XSS patterns
    for pattern in XSS_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning(
                "xss_attempt_detected",
                pattern=pattern,
                value_preview=value[:100]
            )
            raise ValueError("Input contains potentially dangerous XSS patterns")
    
    # HTML escape the string
    return html.escape(value)

def validate_request_size(content_length: Optional[int]) -> None:
    """
    Validate request size to prevent DoS attacks.
    
    Args:
        content_length: Content-Length header value
    
    Raises:
        HTTPException: If request size exceeds limit
    """
    if content_length and content_length > MAX_REQUEST_SIZE:
        logger.warning(
            "request_size_limit_exceeded",
            content_length=content_length,
            max_size=MAX_REQUEST_SIZE
        )
        raise HTTPException(
            status_code=413,
            detail={
                "error": "RequestTooLarge",
                "message": f"Request size exceeds maximum of {MAX_REQUEST_SIZE} bytes",
                "details": {
                    "max_size": MAX_REQUEST_SIZE,
                    "received_size": content_length
                }
            }
        )

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request size limits.
    
    Requirements: 42.2
    """
    
    def __init__(self, app, max_size: int = MAX_REQUEST_SIZE):
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request: Request, call_next):
        """Process request with size validation."""
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size:
                    logger.warning(
                        "request_size_limit_exceeded",
                        content_length=size,
                        max_size=self.max_size,
                        path=request.url.path
                    )
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": "RequestTooLarge",
                            "message": f"Request size exceeds maximum of {self.max_size} bytes",
                            "details": {
                                "max_size": self.max_size,
                                "received_size": size
                            }
                        }
                    )
            except ValueError:
                pass  # Invalid Content-Length, let it through
        
        return await call_next(request)
