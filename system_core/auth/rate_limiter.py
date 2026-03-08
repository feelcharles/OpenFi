"""
Rate limiting implementation for authentication endpoints.

This module provides IP-based rate limiting to prevent brute force attacks
on authentication endpoints.
"""

import time
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

from fastapi import HTTPException, Request, status
from system_core.config import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """
    IP-based rate limiter for authentication endpoints.
    
    Implements sliding window rate limiting with automatic IP blocking
    after exceeding failure threshold.
    """
    
    def __init__(
        self,
        max_attempts: int = 5,
        window_minutes: int = 15,
        block_duration_minutes: int = 30
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_attempts: Maximum login attempts per window
            window_minutes: Time window in minutes
            block_duration_minutes: IP block duration after exceeding attempts
        """
        self.max_attempts = max_attempts
        self.window_seconds = window_minutes * 60
        self.block_duration_seconds = block_duration_minutes * 60
        
        # Store attempt timestamps per IP
        # Format: {ip: [timestamp1, timestamp2, ...]}
        self.attempts: dict[str, list] = defaultdict(list)
        
        # Store blocked IPs
        # Format: {ip: block_expiry_timestamp}
        self.blocked_ips: dict[str, float] = {}
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        logger.info(
            "rate_limiter_initialized",
            max_attempts=max_attempts,
            window_minutes=window_minutes,
            block_duration_minutes=block_duration_minutes
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.
        
        Handles X-Forwarded-For header for proxied requests.
        
        Args:
            request: FastAPI request object
        
        Returns:
            Client IP address
        """
        # Check X-Forwarded-For header (for proxied requests)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP in chain
            return forwarded_for.split(",")[0].strip()
        
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _cleanup_old_attempts(self, ip: str, current_time: float) -> None:
        """
        Remove attempts outside the time window.
        
        Args:
            ip: Client IP address
            current_time: Current timestamp
        """
        if ip in self.attempts:
            cutoff_time = current_time - self.window_seconds
            self.attempts[ip] = [
                ts for ts in self.attempts[ip]
                if ts > cutoff_time
            ]
            
            # Remove IP entry if no recent attempts
            if not self.attempts[ip]:
                del self.attempts[ip]
    
    def _is_blocked(self, ip: str, current_time: float) -> tuple[bool, Optional[float]]:
        """
        Check if IP is currently blocked.
        
        Args:
            ip: Client IP address
            current_time: Current timestamp
        
        Returns:
            Tuple of (is_blocked, remaining_seconds)
        """
        if ip in self.blocked_ips:
            block_expiry = self.blocked_ips[ip]
            
            if current_time < block_expiry:
                # Still blocked
                remaining = block_expiry - current_time
                return True, remaining
            else:
                # Block expired, remove from blocked list
                del self.blocked_ips[ip]
                # Clear attempt history
                if ip in self.attempts:
                    del self.attempts[ip]
        
        return False, None
    
    async def check_rate_limit(self, request: Request) -> None:
        """
        Check if request should be rate limited.
        
        Args:
            request: FastAPI request object
        
        Raises:
            HTTPException: 429 if rate limit exceeded or IP is blocked
        """
        ip = self._get_client_ip(request)
        current_time = time.time()
        
        async with self._lock:
            # Check if IP is blocked
            is_blocked, remaining = self._is_blocked(ip, current_time)
            if is_blocked:
                remaining_minutes = int(remaining / 60)
                logger.warning(
                    "blocked_ip_attempt",
                    ip=ip,
                    remaining_minutes=remaining_minutes
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"IP temporarily blocked. Try again in {remaining_minutes} minutes.",
                )
            
            # Cleanup old attempts
            self._cleanup_old_attempts(ip, current_time)
            
            # Check attempt count
            attempt_count = len(self.attempts[ip])
            
            if attempt_count >= self.max_attempts:
                # Block IP
                block_expiry = current_time + self.block_duration_seconds
                self.blocked_ips[ip] = block_expiry
                
                logger.warning(
                    "ip_blocked_rate_limit",
                    ip=ip,
                    attempt_count=attempt_count,
                    block_duration_minutes=self.block_duration_seconds / 60
                )
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many login attempts. IP blocked for {self.block_duration_seconds / 60} minutes.",
                )
    
    async def record_attempt(self, request: Request, success: bool = False) -> None:
        """
        Record authentication attempt.
        
        Args:
            request: FastAPI request object
            success: Whether the attempt was successful
        """
        ip = self._get_client_ip(request)
        current_time = time.time()
        
        async with self._lock:
            if success:
                # Clear attempts on successful login
                if ip in self.attempts:
                    del self.attempts[ip]
                if ip in self.blocked_ips:
                    del self.blocked_ips[ip]
                
                logger.info("successful_login", ip=ip)
            else:
                # Record failed attempt
                self.attempts[ip].append(current_time)
                attempt_count = len(self.attempts[ip])
                
                logger.warning(
                    "failed_login_attempt",
                    ip=ip,
                    attempt_count=attempt_count,
                    max_attempts=self.max_attempts
                )
    
    def get_remaining_attempts(self, request: Request) -> int:
        """
        Get remaining attempts for IP.
        
        Args:
            request: FastAPI request object
        
        Returns:
            Number of remaining attempts before block
        """
        ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Check if blocked
        is_blocked, _ = self._is_blocked(ip, current_time)
        if is_blocked:
            return 0
        
        # Cleanup and count
        self._cleanup_old_attempts(ip, current_time)
        attempt_count = len(self.attempts.get(ip, []))
        
        return max(0, self.max_attempts - attempt_count)

# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None

def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter

async def check_rate_limit(request: Request) -> None:
    """
    FastAPI dependency for rate limiting.
    
    Args:
        request: FastAPI request object
    
    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    limiter = get_rate_limiter()
    await limiter.check_rate_limit(request)
