"""
Security headers middleware.

Implements security headers to protect against common web vulnerabilities.

Requirements: 42.6, 42.7
"""

from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from system_core.config import get_logger

logger = get_logger(__name__)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Requirements: 42.7
    """
    
    def __init__(
        self,
        app,
        csp_policy: Optional[str] = None,
        allowed_origins: Optional[list[str]] = None
    ):
        """
        Initialize security headers middleware.
        
        Args:
            app: FastAPI application
            csp_policy: Content Security Policy string
            allowed_origins: List of allowed CORS origins
        """
        super().__init__(app)
        
        # Default CSP policy
        if csp_policy is None:
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
        
        self.csp_policy = csp_policy
        self.allowed_origins = allowed_origins or []
        
        logger.info(
            "security_headers_middleware_initialized",
            csp_policy=csp_policy,
            allowed_origins=allowed_origins
        )
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)
        
        # Content-Security-Policy
        # Helps prevent XSS attacks by controlling resource loading
        response.headers["Content-Security-Policy"] = self.csp_policy
        
        # X-Frame-Options
        # Prevents clickjacking attacks by controlling iframe embedding
        response.headers["X-Frame-Options"] = "DENY"
        
        # X-Content-Type-Options
        # Prevents MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Strict-Transport-Security (HSTS)
        # Forces HTTPS connections
        # max-age=31536000 (1 year), includeSubDomains, preload
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        
        # X-XSS-Protection (legacy, but still useful for older browsers)
        # Enables browser's XSS filter
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer-Policy
        # Controls how much referrer information is sent
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions-Policy (formerly Feature-Policy)
        # Controls which browser features can be used
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        
        return response

def get_cors_config(allowed_origins: Optional[list[str]] = None) -> dict:
    """
    Get CORS configuration with whitelist.
    
    Args:
        allowed_origins: List of allowed origins
    
    Returns:
        CORS configuration dictionary
    
    Requirements: 42.6
    """
    if allowed_origins is None:
        # Default to localhost only for security
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080"
        ]
    
    return {
        "allow_origins": allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],
        "expose_headers": [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset"
        ],
        "max_age": 600  # Cache preflight requests for 10 minutes
    }

def validate_origin(origin: str, allowed_origins: list[str]) -> bool:
    """
    Validate if origin is in whitelist.
    
    Args:
        origin: Origin header value
        allowed_origins: List of allowed origins
    
    Returns:
        True if origin is allowed, False otherwise
    """
    if not origin:
        return False
    
    # Check exact match
    if origin in allowed_origins:
        return True
    
    # Check wildcard patterns
    for allowed in allowed_origins:
        if allowed == "*":
            return True
        if allowed.endswith("*"):
            prefix = allowed[:-1]
            if origin.startswith(prefix):
                return True
    
    return False
