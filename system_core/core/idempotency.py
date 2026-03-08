"""
Idempotency Middleware

Provides idempotency key support for API endpoints to prevent duplicate operations.
Stores request hash and response in Redis with 24-hour TTL.
"""

import hashlib
import json
from datetime import timedelta
from typing import Any, Callable, Optional

from fastapi import Header, Request, Response
from fastapi.responses import JSONResponse
import redis.asyncio as redis

from system_core.core.exceptions import EventBusError

class IdempotencyMiddleware:
    """
    Middleware for handling idempotency keys in API requests.
    
    Features:
    - Accept optional Idempotency-Key header in POST/PUT/DELETE requests
    - Store key with request hash and response in Redis (TTL 24 hours)
    - Return cached response for duplicate keys
    """
    
    def __init__(
        self,
        redis_url: str,
        password: Optional[str] = None,
        ttl_seconds: int = 86400,  # 24 hours
        key_prefix: str = "idempotency:"
    ):
        """
        Initialize idempotency middleware.
        
        Args:
            redis_url: Redis connection URL
            password: Redis password (optional)
            ttl_seconds: Time-to-live for cached responses (default 24 hours)
            key_prefix: Prefix for Redis keys
        """
        self.redis_url = redis_url
        self.password = password
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                password=self.password,
                decode_responses=True
            )
            await self.redis_client.ping()
        except Exception as e:
            # Log warning but don't fail - idempotency is optional
            print(f"Warning: Failed to connect to Redis for idempotency: {e}")
            print("Idempotency features will be disabled. System will continue without Redis.")
            self.redis_client = None
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
    
    def _should_check_idempotency(self, method: str) -> bool:
        """Check if request method should use idempotency."""
        return method.upper() in ("POST", "PUT", "DELETE")
    
    def _generate_request_hash(self, request: Request, body: bytes) -> str:
        """
        Generate hash of request for deduplication.
        
        Includes: method, path, query params, and body
        """
        hash_input = f"{request.method}:{request.url.path}:{request.url.query}:{body.decode('utf-8')}"
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    def _get_redis_key(self, idempotency_key: str, request_hash: str) -> str:
        """Generate Redis key for idempotency storage."""
        return f"{self.key_prefix}{idempotency_key}:{request_hash}"
    
    async def check_idempotency(
        self,
        request: Request,
        idempotency_key: Optional[str],
        body: bytes
    ) -> Optional[Response]:
        """
        Check if request with idempotency key has been processed before.
        
        Args:
            request: FastAPI request object
            idempotency_key: Idempotency key from header
            body: Request body bytes
            
        Returns:
            Cached response if found, None otherwise
        """
        # Only check for POST/PUT/DELETE
        if not self._should_check_idempotency(request.method):
            return None
        
        # No idempotency key provided
        if not idempotency_key:
            return None
        
        # Generate request hash
        request_hash = self._generate_request_hash(request, body)
        redis_key = self._get_redis_key(idempotency_key, request_hash)
        
        # Check Redis for cached response
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(redis_key)
                if cached_data:
                    # Parse cached response
                    cached_response = json.loads(cached_data)
                    
                    # Return cached response
                    return JSONResponse(
                        status_code=cached_response.get("status_code", 200),
                        content=cached_response.get("body"),
                        headers={
                            "X-Idempotency-Cached": "true",
                            **cached_response.get("headers", {})
                        }
                    )
            except Exception as e:
                # Log error but don't fail the request
                print(f"Error checking idempotency cache: {e}")
        
        return None
    
    async def store_response(
        self,
        request: Request,
        idempotency_key: Optional[str],
        body: bytes,
        response: Response
    ) -> None:
        """
        Store response in Redis for future idempotency checks.
        
        Args:
            request: FastAPI request object
            idempotency_key: Idempotency key from header
            body: Request body bytes
            response: Response to cache
        """
        # Only store for POST/PUT/DELETE
        if not self._should_check_idempotency(request.method):
            return
        
        # No idempotency key provided
        if not idempotency_key:
            return
        
        # Generate request hash
        request_hash = self._generate_request_hash(request, body)
        redis_key = self._get_redis_key(idempotency_key, request_hash)
        
        # Store response in Redis
        if self.redis_client:
            try:
                # Extract response data
                response_data = {
                    "status_code": response.status_code,
                    "body": response.body.decode('utf-8') if isinstance(response.body, bytes) else response.body,
                    "headers": dict(response.headers)
                }
                
                # Store with TTL
                await self.redis_client.setex(
                    redis_key,
                    self.ttl_seconds,
                    json.dumps(response_data)
                )
            except Exception as e:
                # Log error but don't fail the request
                print(f"Error storing idempotency response: {e}")

class IdempotencyKeyDependency:
    """
    FastAPI dependency for extracting idempotency key from headers.
    """
    
    def __init__(self, middleware: IdempotencyMiddleware):
        """
        Initialize dependency.
        
        Args:
            middleware: IdempotencyMiddleware instance
        """
        self.middleware = middleware
    
    async def __call__(
        self,
        request: Request,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
    ) -> Optional[str]:
        """
        Extract and validate idempotency key from request header.
        
        Args:
            request: FastAPI request object
            idempotency_key: Idempotency key from header
            
        Returns:
            Idempotency key if present, None otherwise
        """
        return idempotency_key

async def idempotency_middleware(
    request: Request,
    call_next: Callable,
    middleware: IdempotencyMiddleware
) -> Response:
    """
    Middleware function to handle idempotency for all requests.
    
    Args:
        request: FastAPI request object
        call_next: Next middleware/handler in chain
        middleware: IdempotencyMiddleware instance
        
    Returns:
        Response (cached or fresh)
    """
    # Read request body
    body = await request.body()
    
    # Extract idempotency key from header
    idempotency_key = request.headers.get("Idempotency-Key")
    
    # Check for cached response
    cached_response = await middleware.check_idempotency(request, idempotency_key, body)
    if cached_response:
        return cached_response
    
    # Process request normally
    response = await call_next(request)
    
    # Store response for future idempotency checks
    await middleware.store_response(request, idempotency_key, body, response)
    
    return response
