"""
Dead Letter Queue Implementation

Handles events that fail processing after maximum retry attempts.
Uses Redis List data structure for storage.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import redis.asyncio as redis
from redis.exceptions import RedisError

from system_core.core.exceptions import EventBusError
from system_core.event_bus.models import Event

logger = logging.getLogger(__name__)

class FailedEvent:
    """
    Represents an event that failed processing.
    
    Tracks retry attempts and error information.
    """
    
    def __init__(
        self,
        event: Event,
        error: str,
        retry_count: int = 0,
        first_failure_time: Optional[datetime] = None,
        last_failure_time: Optional[datetime] = None
    ):
        """
        Initialize failed event.
        
        Args:
            event: Original event that failed
            error: Error message
            retry_count: Number of retry attempts
            first_failure_time: Time of first failure
            last_failure_time: Time of last failure
        """
        self.event = event
        self.error = error
        self.retry_count = retry_count
        self.first_failure_time = first_failure_time or datetime.utcnow()
        self.last_failure_time = last_failure_time or datetime.utcnow()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "event": self.event.model_dump(),
            "error": self.error,
            "retry_count": self.retry_count,
            "first_failure_time": self.first_failure_time.isoformat(),
            "last_failure_time": self.last_failure_time.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FailedEvent":
        """Create from dictionary."""
        event = Event(**data["event"])
        return cls(
            event=event,
            error=data["error"],
            retry_count=data["retry_count"],
            first_failure_time=datetime.fromisoformat(data["first_failure_time"]),
            last_failure_time=datetime.fromisoformat(data["last_failure_time"])
        )

class DeadLetterQueue:
    """
    Dead Letter Queue for failed events.
    
    Uses Redis List to store events that fail processing after maximum retry attempts.
    Tracks retry attempts and error information for each event.
    """
    
    # Redis key for DLQ
    DLQ_KEY = "event_bus:dead_letter_queue"
    
    # Redis key for retry tracking
    RETRY_TRACKING_KEY_PREFIX = "event_bus:retry:"
    
    def __init__(
        self,
        redis_client: redis.Redis,
        max_retry_attempts: int = 3,
        retry_delay_seconds: int = 60,
        retry_backoff_multiplier: int = 2,
        retention_days: int = 7,
        max_size: int = 10000
    ):
        """
        Initialize Dead Letter Queue.
        
        Args:
            redis_client: Redis client instance
            max_retry_attempts: Maximum retry attempts before moving to DLQ
            retry_delay_seconds: Initial retry delay in seconds
            retry_backoff_multiplier: Backoff multiplier for retries
            retention_days: How long to keep events in DLQ
            max_size: Maximum DLQ size
        """
        self.redis_client = redis_client
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.retry_backoff_multiplier = retry_backoff_multiplier
        self.retention_days = retention_days
        self.max_size = max_size
    
    async def track_failure(self, event: Event, error: str) -> bool:
        """
        Track event failure and determine if it should be moved to DLQ.
        
        Args:
            event: Event that failed processing
            error: Error message
            
        Returns:
            True if event should be moved to DLQ, False if it should be retried
        """
        retry_key = f"{self.RETRY_TRACKING_KEY_PREFIX}{event.event_id}"
        
        try:
            # Get current retry count
            retry_data = await self.redis_client.get(retry_key)
            
            if retry_data:
                # Parse existing retry data
                failed_event = FailedEvent.from_dict(json.loads(retry_data))
                failed_event.retry_count += 1
                failed_event.last_failure_time = datetime.utcnow()
                failed_event.error = error  # Update with latest error
            else:
                # First failure
                failed_event = FailedEvent(
                    event=event,
                    error=error,
                    retry_count=1
                )
            
            # Check if max retries exceeded
            if failed_event.retry_count > self.max_retry_attempts:
                # Move to DLQ
                await self._add_to_dlq(failed_event)
                
                # Remove retry tracking
                await self.redis_client.delete(retry_key)
                
                logger.error(
                    f"Event {event.event_id} moved to DLQ after {failed_event.retry_count} failed attempts. "
                    f"Error: {error}"
                )
                
                return True
            else:
                # Update retry tracking with TTL
                ttl_seconds = self._calculate_retry_delay(failed_event.retry_count) * 2
                await self.redis_client.setex(
                    retry_key,
                    ttl_seconds,
                    json.dumps(failed_event.to_dict(), default=str)
                )
                
                logger.warning(
                    f"Event {event.event_id} failed (attempt {failed_event.retry_count}/{self.max_retry_attempts}). "
                    f"Error: {error}"
                )
                
                return False
        
        except RedisError as e:
            logger.error(f"Failed to track event failure: {e}")
            # On Redis error, don't move to DLQ to avoid data loss
            return False
    
    async def _add_to_dlq(self, failed_event: FailedEvent) -> None:
        """
        Add failed event to Dead Letter Queue.
        
        Args:
            failed_event: Failed event to add
        """
        try:
            # Serialize failed event
            data = json.dumps(failed_event.to_dict(), default=str)
            
            # Add to DLQ (Redis List - push to right)
            await self.redis_client.rpush(self.DLQ_KEY, data)
            
            # Trim DLQ if it exceeds max size (keep most recent)
            await self.redis_client.ltrim(self.DLQ_KEY, -self.max_size, -1)
            
            # Set expiration on DLQ key (refresh on each add)
            retention_seconds = self.retention_days * 24 * 60 * 60
            await self.redis_client.expire(self.DLQ_KEY, retention_seconds)
        
        except RedisError as e:
            raise EventBusError(f"Failed to add event to DLQ: {e}")
    
    async def get_failed_events(
        self,
        start: int = 0,
        end: int = -1
    ) -> list[FailedEvent]:
        """
        Get failed events from DLQ.
        
        Args:
            start: Start index (0-based)
            end: End index (-1 for all)
            
        Returns:
            List of failed events
        """
        try:
            # Get events from Redis List
            events_data = await self.redis_client.lrange(self.DLQ_KEY, start, end)
            
            # Parse events
            failed_events = []
            for data in events_data:
                try:
                    failed_event = FailedEvent.from_dict(json.loads(data))
                    failed_events.append(failed_event)
                except Exception as e:
                    logger.error(f"Failed to parse DLQ event: {e}")
            
            return failed_events
        
        except RedisError as e:
            raise EventBusError(f"Failed to get events from DLQ: {e}")
    
    async def get_dlq_size(self) -> int:
        """
        Get current DLQ size.
        
        Returns:
            Number of events in DLQ
        """
        try:
            return await self.redis_client.llen(self.DLQ_KEY)
        except RedisError as e:
            logger.error(f"Failed to get DLQ size: {e}")
            return 0
    
    async def remove_event(self, event_id: UUID) -> bool:
        """
        Remove specific event from DLQ.
        
        Args:
            event_id: Event ID to remove
            
        Returns:
            True if event was removed, False otherwise
        """
        try:
            # Get all events
            events_data = await self.redis_client.lrange(self.DLQ_KEY, 0, -1)
            
            # Find and remove matching event
            for data in events_data:
                try:
                    failed_event = FailedEvent.from_dict(json.loads(data))
                    if failed_event.event.event_id == event_id:
                        # Remove from list (lrem removes all occurrences)
                        await self.redis_client.lrem(self.DLQ_KEY, 1, data)
                        logger.info(f"Removed event {event_id} from DLQ")
                        return True
                except Exception as e:
                    logger.error(f"Failed to parse DLQ event: {e}")
            
            return False
        
        except RedisError as e:
            logger.error(f"Failed to remove event from DLQ: {e}")
            return False
    
    async def clear_dlq(self) -> int:
        """
        Clear all events from DLQ.
        
        Returns:
            Number of events cleared
        """
        try:
            size = await self.get_dlq_size()
            await self.redis_client.delete(self.DLQ_KEY)
            logger.info(f"Cleared {size} events from DLQ")
            return size
        except RedisError as e:
            logger.error(f"Failed to clear DLQ: {e}")
            return 0
    
    async def cleanup_old_events(self) -> int:
        """
        Remove events older than retention period from DLQ.
        
        Returns:
            Number of events removed
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=self.retention_days)
            
            # Get all events
            events_data = await self.redis_client.lrange(self.DLQ_KEY, 0, -1)
            
            removed_count = 0
            for data in events_data:
                try:
                    failed_event = FailedEvent.from_dict(json.loads(data))
                    
                    # Check if event is older than retention period
                    if failed_event.first_failure_time < cutoff_time:
                        await self.redis_client.lrem(self.DLQ_KEY, 1, data)
                        removed_count += 1
                
                except Exception as e:
                    logger.error(f"Failed to parse DLQ event during cleanup: {e}")
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old events from DLQ")
            
            return removed_count
        
        except RedisError as e:
            logger.error(f"Failed to cleanup old events from DLQ: {e}")
            return 0
    
    def _calculate_retry_delay(self, retry_count: int) -> int:
        """
        Calculate retry delay with exponential backoff.
        
        Args:
            retry_count: Current retry attempt number
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff: delay * (multiplier ^ (retry_count - 1))
        return self.retry_delay_seconds * (self.retry_backoff_multiplier ** (retry_count - 1))
    
    async def get_retry_count(self, event_id: UUID) -> int:
        """
        Get current retry count for an event.
        
        Args:
            event_id: Event ID
            
        Returns:
            Current retry count (0 if not tracked)
        """
        retry_key = f"{self.RETRY_TRACKING_KEY_PREFIX}{event_id}"
        
        try:
            retry_data = await self.redis_client.get(retry_key)
            
            if retry_data:
                failed_event = FailedEvent.from_dict(json.loads(retry_data))
                return failed_event.retry_count
            
            return 0
        
        except Exception as e:
            logger.error(f"Failed to get retry count: {e}")
            return 0
