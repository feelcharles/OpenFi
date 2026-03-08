"""
Data Fetcher Base Class

Abstract base class for data fetchers with retry logic, duplicate detection, and rate limiting.

Validates: Requirements 2.4, 2.6, 38.3, 38.5, 38.6
"""

import asyncio
import hashlib
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from decimal import Decimal
import uuid

import aiohttp

from system_core.config import get_logger
from system_core.event_bus import EventBus, RawDataEvent

logger = get_logger(__name__)

class TokenBucket:
    """
    Token bucket algorithm for rate limiting.
    
    Validates: Requirement 38.3
    """
    
    def __init__(self, rate: int, capacity: int):
        """
        Initialize token bucket.
        
        Args:
            rate: Tokens added per minute
            capacity: Maximum tokens in bucket
        """
        self.rate = rate  # tokens per minute
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens from bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens acquired, False if rate limit exceeded
        """
        async with self.lock:
            # Refill tokens based on time elapsed
            now = time.time()
            elapsed = now - self.last_refill
            
            # Add tokens based on rate (tokens per minute)
            tokens_to_add = (elapsed / 60.0) * self.rate
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now
            
            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def get_remaining_quota(self) -> int:
        """Get remaining tokens in bucket."""
        return int(self.tokens)
    
    def get_reset_time(self) -> float:
        """Get time until bucket is full (in seconds)."""
        if self.tokens >= self.capacity:
            return 0.0
        
        tokens_needed = self.capacity - self.tokens
        seconds_needed = (tokens_needed / self.rate) * 60.0
        return seconds_needed

class RawData:
    """Standard format for fetched data."""
    
    def __init__(
        self,
        source: str,
        source_type: str,
        timestamp: datetime,
        data_type: str,
        content: dict[str, Any],
        metadata: dict[str, Any],
        quality_score: float = 100.0
    ):
        self.source = source
        self.source_type = source_type
        self.timestamp = timestamp
        self.data_type = data_type
        self.content = content
        self.metadata = metadata
        self.quality_score = quality_score
        self.fetch_time = datetime.utcnow()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for event publishing."""
        return {
            "source": self.source,
            "source_type": self.source_type,
            "timestamp": self.timestamp.isoformat(),
            "data_type": self.data_type,
            "content": self.content,
            "metadata": {
                **self.metadata,
                "fetch_time": self.fetch_time.isoformat(),
                "quality_score": self.quality_score
            }
        }
    
    def get_unique_id(self) -> str:
        """
        Generate unique identifier for duplicate detection.
        
        Uses: source + external_id + timestamp
        
        Validates: Requirement 2.4
        """
        external_id = self.content.get("id", self.content.get("external_id", ""))
        unique_string = f"{self.source}:{external_id}:{self.timestamp.isoformat()}"
        return hashlib.sha256(unique_string.encode()).hexdigest()

class DataFetcher(ABC):
    """
    Abstract base class for data fetchers.
    
    Provides:
    - Retry logic with exponential backoff
    - Duplicate detection
    - Event publishing
    - Error handling
    """
    
    def __init__(
        self,
        source_config: dict[str, Any],
        event_bus: EventBus
    ):
        """
        Initialize data fetcher.
        
        Args:
            source_config: Source configuration from fetch_sources.yaml
            event_bus: Event bus for publishing data
        """
        self.source_config = source_config
        self.event_bus = event_bus
        
        self.source_id = source_config["source_id"]
        self.source_type = source_config["source_type"]
        self.api_endpoint = source_config["api_endpoint"]
        self.credentials = source_config.get("credentials", {})
        self.retry_count = source_config.get("retry_count", 3)
        self.timeout = source_config.get("timeout", 30)
        self.parameters = source_config.get("parameters", {})
        
        # Priority for graceful degradation (Requirement 38.8)
        # critical, high, normal, low
        self.priority = source_config.get("priority", "normal")
        
        # Rate limiting configuration (Requirement 38.5)
        rate_limit_config = source_config.get("rate_limit", {})
        self.rate_limit_enabled = rate_limit_config.get("enabled", False)
        
        if self.rate_limit_enabled:
            rate = rate_limit_config.get("requests_per_minute", 60)
            capacity = rate_limit_config.get("burst_capacity", rate)
            self.rate_limiter = TokenBucket(rate=rate, capacity=capacity)
            logger.info(
                f"Rate limiting enabled for {self.source_id}: {rate} req/min",
                extra={"source_id": self.source_id, "rate": rate}
            )
        else:
            self.rate_limiter = None
        
        # Duplicate detection cache (in-memory, could be Redis in production)
        self.seen_ids: set[str] = set()
        
        # Metrics tracking (Requirement 38.7)
        self.metrics = {
            "total_requests": 0,
            "successful_fetches": 0,
            "failed_fetches": 0,
            "duplicate_count": 0,
            "total_response_time": 0.0,
            "rate_limit_hits": 0,
            "skipped_non_critical": 0
        }
        
        logger.info(
            f"DataFetcher initialized for {self.source_id}",
            extra={"source_id": self.source_id, "source_type": self.source_type, "priority": self.priority}
        )
    
    @abstractmethod
    async def fetch(self) -> dict[str, Any]:
        """
        Fetch data from external source.
        
        Returns:
            Raw API response
            
        Validates: Requirement 2.2
        """
        pass
    
    @abstractmethod
    def transform(self, raw_data: dict[str, Any]) -> RawData:
        """
        Transform raw API response to standard format.
        
        Args:
            raw_data: Raw API response
            
        Returns:
            Standardized RawData object
            
        Validates: Requirement 2.3
        """
        pass
    
    async def retry_with_backoff(
        self,
        func,
        *args,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        multiplier: float = 2.0,
        **kwargs
    ) -> Any:
        """
        Execute function with exponential backoff retry.
        
        Args:
            func: Async function to execute
            max_attempts: Maximum retry attempts
            initial_delay: Initial delay in seconds
            multiplier: Backoff multiplier
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries fail
            
        Validates: Requirement 2.6
        """
        delay = initial_delay
        last_exception = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            
            except Exception as e:
                last_exception = e
                
                if attempt < max_attempts:
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {self.source_id}, "
                        f"retrying in {delay}s: {e}",
                        extra={
                            "source_id": self.source_id,
                            "attempt": attempt,
                            "delay": delay,
                            "error": str(e)
                        }
                    )
                    await asyncio.sleep(delay)
                    delay *= multiplier
                else:
                    logger.error(
                        f"All {max_attempts} attempts failed for {self.source_id}: {e}",
                        extra={
                            "source_id": self.source_id,
                            "max_attempts": max_attempts,
                            "error": str(e)
                        }
                    )
        
        raise last_exception
    
    async def wait_for_rate_limit(self) -> None:
        """
        Wait for rate limit with exponential backoff.
        
        Implements exponential backoff when rate limit is exceeded.
        
        Validates: Requirement 38.6
        """
        if not self.rate_limiter:
            return
        
        # Try to acquire token
        if await self.rate_limiter.acquire():
            return
        
        # Rate limit exceeded - implement exponential backoff
        self.metrics["rate_limit_hits"] += 1
        
        delay = 1.0  # Initial delay of 1 second (Requirement 38.6)
        max_delay = 60.0  # Maximum delay of 1 minute
        
        while True:
            logger.warning(
                f"Rate limit exceeded for {self.source_id}, waiting {delay}s",
                extra={
                    "source_id": self.source_id,
                    "delay": delay,
                    "remaining_quota": self.rate_limiter.get_remaining_quota(),
                    "reset_time": self.rate_limiter.get_reset_time()
                }
            )
            
            await asyncio.sleep(delay)
            
            # Try to acquire token again
            if await self.rate_limiter.acquire():
                logger.info(
                    f"Rate limit cleared for {self.source_id}",
                    extra={"source_id": self.source_id}
                )
                return
            
            # Exponential backoff
            delay = min(delay * 2, max_delay)
    
    def is_duplicate(self, raw_data: RawData) -> bool:
        """
        Check if data is duplicate based on unique identifier.
        
        Args:
            raw_data: RawData object
            
        Returns:
            True if duplicate, False otherwise
            
        Validates: Requirement 2.4
        """
        unique_id = raw_data.get_unique_id()
        
        if unique_id in self.seen_ids:
            self.metrics["duplicate_count"] += 1
            logger.debug(
                f"Duplicate data detected for {self.source_id}",
                extra={
                    "source_id": self.source_id,
                    "unique_id": unique_id
                }
            )
            return True
        
        self.seen_ids.add(unique_id)
        return False
    
    async def publish(self, data: RawData) -> None:
        """
        Publish transformed data to event bus.
        
        Args:
            data: RawData object
            
        Validates: Requirement 2.7
        """
        # Check for duplicates
        if self.is_duplicate(data):
            logger.info(
                f"Skipping duplicate data from {self.source_id}",
                extra={"source_id": self.source_id}
            )
            return
        
        # Publish to event bus
        topic = f"data.raw.{self.source_type}"
        
        try:
            await self.event_bus.publish(topic, data.to_dict())
            
            logger.info(
                f"Published data from {self.source_id} to {topic}",
                extra={
                    "source_id": self.source_id,
                    "topic": topic,
                    "data_type": data.data_type
                }
            )
        
        except Exception as e:
            logger.error(
                f"Failed to publish data from {self.source_id}: {e}",
                extra={
                    "source_id": self.source_id,
                    "topic": topic,
                    "error": str(e)
                },
                exc_info=True
            )
            raise
    
    async def fetch_and_publish(self) -> None:
        """
        Main execution flow: fetch, transform, and publish data.
        
        Validates: Requirements 2.2, 2.3, 2.5, 2.7, 2.8, 38.5, 38.6, 38.8
        """
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            # Check if we should skip non-critical processing (Requirement 38.8)
            if self.priority in ["low", "normal"] and self._should_skip_non_critical():
                self.metrics["skipped_non_critical"] += 1
                logger.info(
                    f"Skipping non-critical fetch for {self.source_id} due to system overload",
                    extra={
                        "trace_id": trace_id,
                        "source_id": self.source_id,
                        "priority": self.priority
                    }
                )
                return
            
            self.metrics["total_requests"] += 1
            
            # Wait for rate limit if enabled (Requirement 38.5, 38.6)
            await self.wait_for_rate_limit()
            
            # Fetch data with retry
            raw_response = await self.retry_with_backoff(
                self.fetch,
                max_attempts=self.retry_count
            )
            
            # Transform to standard format
            raw_data = self.transform(raw_response)
            
            # Publish to event bus
            await self.publish(raw_data)
            
            # Update metrics
            end_time = datetime.utcnow()
            response_time = (end_time - start_time).total_seconds()
            self.metrics["successful_fetches"] += 1
            self.metrics["total_response_time"] += response_time
            
            logger.info(
                f"Fetch and publish completed for {self.source_id}",
                extra={
                    "trace_id": trace_id,
                    "source_id": self.source_id,
                    "response_time": response_time
                }
            )
        
        except Exception as e:
            self.metrics["failed_fetches"] += 1
            
            # Log error with full details (Requirement 2.5)
            logger.error(
                f"Fetch and publish failed for {self.source_id}: {e}",
                extra={
                    "trace_id": trace_id,
                    "source_id": self.source_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise
    
    def _should_skip_non_critical(self) -> bool:
        """
        Check if non-critical processing should be skipped.
        
        This would check system load indicators like:
        - Event Bus queue depth
        - CPU/memory usage
        - Error rates
        
        Returns:
            True if processing should be skipped, False otherwise
            
        Validates: Requirement 38.8
        """
        # Check Event Bus backpressure
        # In a real implementation, this would query the Event Bus
        # for queue depth and other load indicators
        
        # For now, return False (don't skip)
        # This can be enhanced with actual system metrics
        return False
    
    def get_metrics(self) -> dict[str, Any]:
        """
        Get fetcher metrics.
        
        Returns:
            Dictionary with metrics including rate limit info
            
        Validates: Requirements 2.8, 38.7
        """
        avg_response_time = (
            self.metrics["total_response_time"] / self.metrics["successful_fetches"]
            if self.metrics["successful_fetches"] > 0
            else 0.0
        )
        
        metrics = {
            "source_id": self.source_id,
            "total_requests": self.metrics["total_requests"],
            "successful_fetches": self.metrics["successful_fetches"],
            "failed_fetches": self.metrics["failed_fetches"],
            "duplicate_count": self.metrics["duplicate_count"],
            "average_response_time": round(avg_response_time, 3)
        }
        
        # Add rate limit metrics if enabled (Requirement 38.7)
        if self.rate_limiter:
            metrics.update({
                "rate_limit_enabled": True,
                "current_rate": self.rate_limiter.rate,
                "limit": self.rate_limiter.capacity,
                "remaining_quota": self.rate_limiter.get_remaining_quota(),
                "reset_time": round(self.rate_limiter.get_reset_time(), 2),
                "rate_limit_hits": self.metrics["rate_limit_hits"]
            })
        else:
            metrics["rate_limit_enabled"] = False
        
        return metrics
