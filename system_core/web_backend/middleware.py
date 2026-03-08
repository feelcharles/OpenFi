"""
Middleware for Web Backend API.

Provides rate limiting and CORS configuration.
"""

from datetime import datetime, timedelta

from collections import defaultdict
import asyncio

from fastapi import Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from system_core.config import get_logger

logger = get_logger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.
    
    Limits requests to 100 per minute per user.
    
    Requirements: 21.6
    """
    
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.user_requests: dict[str, list] = defaultdict(list)
        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self.cleanup_old_entries())
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for health check
        if request.url.path == "/health":
            return await call_next(request)
        
        # Get user identifier (from JWT or IP address)
        user_id = self._get_user_identifier(request)
        
        # Check rate limit
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old requests
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if req_time > minute_ago
        ]
        
        # Check if limit exceeded
        if len(self.user_requests[user_id]) >= self.requests_per_minute:
            logger.warning(
                "rate_limit_exceeded",
                user_id=user_id,
                path=request.url.path,
                count=len(self.user_requests[user_id])
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RateLimitExceeded",
                    "message": f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                    "details": {
                        "limit": self.requests_per_minute,
                        "window": "1 minute",
                        "retry_after": 60
                    },
                    "timestamp": now.isoformat()
                }
            )
        
        # Add current request
        self.user_requests[user_id].append(now)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            self.requests_per_minute - len(self.user_requests[user_id])
        )
        response.headers["X-RateLimit-Reset"] = str(int((now + timedelta(minutes=1)).timestamp()))
        
        return response
    
    def _get_user_identifier(self, request: Request) -> str:
        """Get user identifier from request."""
        # Try to get user from JWT token
        if hasattr(request.state, "user") and request.state.user:
            return str(request.state.user.id)
        
        # Fallback to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        return request.client.host if request.client else "unknown"
    
    async def cleanup_old_entries(self):
        """Periodically cleanup old entries to prevent memory leak."""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                now = datetime.utcnow()
                minute_ago = now - timedelta(minutes=1)
                
                # Remove users with no recent requests
                users_to_remove = []
                for user_id, requests in self.user_requests.items():
                    self.user_requests[user_id] = [
                        req_time for req_time in requests
                        if req_time > minute_ago
                    ]
                    if not self.user_requests[user_id]:
                        users_to_remove.append(user_id)
                
                for user_id in users_to_remove:
                    del self.user_requests[user_id]
                
                logger.debug("rate_limit_cleanup", active_users=len(self.user_requests))
            except asyncio.CancelledError:
                logger.info("rate_limit_cleanup_cancelled")
                break
            except Exception as e:
                logger.error("rate_limit_cleanup_error", error=str(e))

def setup_cors(app, allowed_origins: list = None):
    """
    Setup CORS middleware.
    
    Args:
        app: FastAPI application
        allowed_origins: List of allowed origins (default: localhost only)
    
    Requirements: 21.7
    """
    if allowed_origins is None:
        allowed_origins = [
            "http://localhost:3000",
            "http://localhost:8080",
            "http://localhost:8686",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
            "http://127.0.0.1:8686"
        ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Requested-With",
            "X-Idempotency-Key",
            "Accept",
            "Origin"
        ],
        expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
    )
    
    logger.info("cors_configured", allowed_origins=allowed_origins)
