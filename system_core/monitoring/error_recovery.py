"""
Error recovery strategies for resilient operations.

Validates: Requirements 24.7
"""

import asyncio
import time
from typing import Callable, TypeVar, Optional, Any, Type
from functools import wraps
from .logger import get_logger, log_exception

logger = get_logger(__name__)

T = TypeVar('T')

class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass

async def retry_with_backoff(
    func: Callable[..., T],
    *args,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,),
    **kwargs
) -> T:
    """
    Retry function with exponential backoff for transient errors.
    
    Args:
        func: Function to retry (can be sync or async)
        *args: Positional arguments for func
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        backoff_multiplier: Multiplier for exponential backoff
        max_delay: Maximum delay between retries
        exceptions: Tuple of exception types to catch and retry
        **kwargs: Keyword arguments for func
        
    Returns:
        Result of successful function call
        
    Raises:
        RetryExhaustedError: If all retry attempts are exhausted
        
    Validates: Requirements 24.7
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            # Check if function is async
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            if attempt > 1:
                logger.info(
                    "retry_succeeded",
                    function=func.__name__,
                    attempt=attempt,
                    max_attempts=max_attempts
                )
            
            return result
            
        except exceptions as e:
            last_exception = e
            
            if attempt == max_attempts:
                logger.error(
                    "retry_exhausted",
                    function=func.__name__,
                    attempts=attempt,
                    max_attempts=max_attempts,
                    exception_type=type(e).__name__,
                    exception_message=str(e)
                )
                raise RetryExhaustedError(
                    f"Failed after {max_attempts} attempts: {str(e)}"
                ) from e
            
            logger.warning(
                "retry_attempt_failed",
                function=func.__name__,
                attempt=attempt,
                max_attempts=max_attempts,
                delay=delay,
                exception_type=type(e).__name__,
                exception_message=str(e)
            )
            
            # Wait before next retry
            if asyncio.iscoroutinefunction(func):
                await asyncio.sleep(delay)
            else:
                time.sleep(delay)
            
            # Calculate next delay with exponential backoff
            delay = min(delay * backoff_multiplier, max_delay)
    
    # Should never reach here, but just in case
    raise RetryExhaustedError(f"Failed after {max_attempts} attempts")

def with_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator to add retry with exponential backoff to a function.
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        backoff_multiplier: Multiplier for exponential backoff
        max_delay: Maximum delay between retries
        exceptions: Tuple of exception types to catch and retry
        
    Example:
        @with_retry(max_attempts=3, initial_delay=1.0)
        async def fetch_data():
            # ... code that might fail transiently
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await retry_with_backoff(
                func, *args,
                max_attempts=max_attempts,
                initial_delay=initial_delay,
                backoff_multiplier=backoff_multiplier,
                max_delay=max_delay,
                exceptions=exceptions,
                **kwargs
            )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run in event loop
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                retry_with_backoff(
                    func, *args,
                    max_attempts=max_attempts,
                    initial_delay=initial_delay,
                    backoff_multiplier=backoff_multiplier,
                    max_delay=max_delay,
                    exceptions=exceptions,
                    **kwargs
                )
            )
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

class FallbackHandler:
    """
    Handler for fallback strategies when primary service is unavailable.
    
    Validates: Requirements 24.7
    """
    
    def __init__(self, primary: Callable, fallback: Callable, name: str = "service"):
        """
        Initialize fallback handler.
        
        Args:
            primary: Primary function to call
            fallback: Fallback function to call if primary fails
            name: Service name for logging
        """
        self.primary = primary
        self.fallback = fallback
        self.name = name
    
    async def execute(self, *args, **kwargs) -> Any:
        """
        Execute with fallback strategy.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Result from primary or fallback function
        """
        try:
            # Try primary function
            if asyncio.iscoroutinefunction(self.primary):
                result = await self.primary(*args, **kwargs)
            else:
                result = self.primary(*args, **kwargs)
            
            return result
            
        except Exception as e:
            logger.warning(
                "fallback_triggered",
                service=self.name,
                exception_type=type(e).__name__,
                exception_message=str(e)
            )
            
            try:
                # Try fallback function
                if asyncio.iscoroutinefunction(self.fallback):
                    result = await self.fallback(*args, **kwargs)
                else:
                    result = self.fallback(*args, **kwargs)
                
                logger.info(
                    "fallback_succeeded",
                    service=self.name
                )
                
                return result
                
            except Exception as fallback_error:
                logger.error(
                    "fallback_failed",
                    service=self.name,
                    exception_type=type(fallback_error).__name__,
                    exception_message=str(fallback_error)
                )
                raise

class SimpleCircuitBreaker:
    """
    Simple circuit breaker for repeated failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are rejected
    - HALF_OPEN: Testing if service recovered
    
    Validates: Requirements 24.7
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        name: str = "circuit"
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            name: Circuit breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.state == "OPEN" and self.last_failure_time:
            return time.time() - self.last_failure_time >= self.recovery_timeout
        return False
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Result of function call
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        # Check if we should attempt reset
        if self._should_attempt_reset():
            self.state = "HALF_OPEN"
            logger.info(
                "circuit_breaker_half_open",
                name=self.name
            )
        
        # Reject if circuit is open
        if self.state == "OPEN":
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open"
            )
        
        try:
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - reset failure count
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info(
                    "circuit_breaker_closed",
                    name=self.name
                )
            
            return result
            
        except Exception as e:
            # Failure - increment count
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(
                    "circuit_breaker_opened",
                    name=self.name,
                    failure_count=self.failure_count,
                    threshold=self.failure_threshold
                )
            
            raise
    
    def reset(self) -> None:
        """Manually reset circuit breaker."""
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = None
        logger.info(
            "circuit_breaker_reset",
            name=self.name
        )
