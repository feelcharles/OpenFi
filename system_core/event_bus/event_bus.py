"""
Event Bus Implementation

Redis-based publish-subscribe event bus for inter-module communication.
Provides connection pooling, topic-based routing, and event serialization.
"""

import asyncio
import json
import signal
import time
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Optional, Pattern
from uuid import UUID, uuid4

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError

from system_core.core.exceptions import EventBusError
from system_core.event_bus.models import Event
from system_core.event_bus.serializer import EventSerializer
from system_core.event_bus.dead_letter_queue import DeadLetterQueue
from system_core.event_bus.metrics import EventMetrics

class EventBus:
    """
    Redis-based event bus for asynchronous inter-module communication.
    
    Features:
    - Connection pooling (min 5, max 20 connections)
    - Pub/sub pattern with topic-based routing
    - Event serialization/deserialization with JSON encoder
    - Message deduplication based on event_id (at-least-once delivery)
    - Graceful shutdown with 30-second wait period
    """
    
    def __init__(
        self,
        redis_url: str,
        password: Optional[str] = None,
        pool_min_size: int = 5,
        pool_max_size: int = 20,
        connection_timeout: int = 30,
        socket_timeout: int = 30,
        socket_keepalive: bool = True,
        retry_on_timeout: bool = True,
        health_check_interval: int = 30,
        dlq_enabled: bool = True,
        dlq_max_retry_attempts: int = 3,
        dlq_retry_delay_seconds: int = 60,
        dlq_retry_backoff_multiplier: int = 2,
        dlq_retention_days: int = 7,
        dlq_max_size: int = 10000,
        metrics_enabled: bool = True,
        metrics_port: int = 8001,
        deduplication_enabled: bool = True,
        deduplication_ttl_seconds: int = 3600,
        max_queue_depth_per_topic: int = 10000
    ):
        """
        Initialize Event Bus with Redis connection pooling.
        
        Args:
            redis_url: Redis connection URL
            password: Redis password (optional)
            pool_min_size: Minimum connections in pool
            pool_max_size: Maximum connections in pool
            connection_timeout: Connection timeout in seconds
            socket_timeout: Socket timeout in seconds
            socket_keepalive: Enable socket keepalive
            retry_on_timeout: Retry on timeout
            health_check_interval: Health check interval in seconds
            dlq_enabled: Enable Dead Letter Queue
            dlq_max_retry_attempts: Maximum retry attempts before moving to DLQ
            dlq_retry_delay_seconds: Initial retry delay in seconds
            dlq_retry_backoff_multiplier: Backoff multiplier for retries
            dlq_retention_days: How long to keep events in DLQ
            dlq_max_size: Maximum DLQ size
            metrics_enabled: Enable Prometheus metrics
            metrics_port: Port for metrics endpoint
            deduplication_enabled: Enable message deduplication
            deduplication_ttl_seconds: TTL for deduplication tracking (default 1 hour)
            max_queue_depth_per_topic: Maximum queue depth per topic for backpressure (default 10000)
        """
        self.redis_url = redis_url
        self.password = password
        self.pool_min_size = pool_min_size
        self.pool_max_size = pool_max_size
        
        # Backpressure configuration
        self.max_queue_depth_per_topic = max_queue_depth_per_topic
        self.queue_depth_key_prefix = "event_queue_depth:"
        
        # Create connection pool
        self.pool = ConnectionPool.from_url(
            redis_url,
            password=password,
            max_connections=pool_max_size,
            socket_timeout=socket_timeout,
            socket_connect_timeout=connection_timeout,
            socket_keepalive=socket_keepalive,
            retry_on_timeout=retry_on_timeout,
            health_check_interval=health_check_interval,
            decode_responses=False  # We handle encoding/decoding ourselves
        )
        
        # Redis clients
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub_client: Optional[redis.client.PubSub] = None
        
        # Subscriber registry: pattern -> list of handlers
        self.subscribers: dict[str, list[Callable]] = {}
        
        # Serializer for event encoding/decoding
        self.serializer = EventSerializer()
        
        # Dead Letter Queue
        self.dlq_enabled = dlq_enabled
        self.dlq: Optional[DeadLetterQueue] = None
        self.dlq_config = {
            'max_retry_attempts': dlq_max_retry_attempts,
            'retry_delay_seconds': dlq_retry_delay_seconds,
            'retry_backoff_multiplier': dlq_retry_backoff_multiplier,
            'retention_days': dlq_retention_days,
            'max_size': dlq_max_size
        }
        
        # Message deduplication
        self.deduplication_enabled = deduplication_enabled
        self.deduplication_ttl_seconds = deduplication_ttl_seconds
        self.deduplication_key_prefix = "event_dedup:"
        
        # Metrics
        self.metrics_enabled = metrics_enabled
        self.metrics: Optional[EventMetrics] = None
        if metrics_enabled:
            self.metrics = EventMetrics(port=metrics_port)
        
        # Shutdown flag
        self._shutdown_requested = False
        self._in_flight_messages = 0
        self._shutdown_event = asyncio.Event()
        
        # Background tasks
        self._subscriber_task: Optional[asyncio.Task] = None
        
    async def connect(self) -> None:
        """Establish connection to Redis."""
        try:
            self.redis_client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            await self.redis_client.ping()
            
            # Create pubsub client
            self.pubsub_client = self.redis_client.pubsub()
            
            # Initialize Dead Letter Queue if enabled
            if self.dlq_enabled:
                self.dlq = DeadLetterQueue(
                    redis_client=self.redis_client,
                    **self.dlq_config
                )
            
            # Start metrics server if enabled
            if self.metrics_enabled and self.metrics:
                self.metrics.start_server()
            
        except RedisError as e:
            raise EventBusError(f"Failed to connect to Redis: {e}")
    
    async def disconnect(self) -> None:
        """Close Redis connections."""
        if self.pubsub_client:
            await self.pubsub_client.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        if self.pool:
            await self.pool.disconnect()
    
    async def _is_duplicate_message(self, event_id: UUID) -> bool:
        """
        Check if message with given event_id has been processed before.
        
        Args:
            event_id: Event identifier
            
        Returns:
            True if message is duplicate, False otherwise
        """
        if not self.deduplication_enabled or not self.redis_client:
            return False
        
        dedup_key = f"{self.deduplication_key_prefix}{str(event_id)}"
        
        try:
            # Check if key exists
            exists = await self.redis_client.exists(dedup_key)
            return exists > 0
        except RedisError as e:
            # Log error but don't fail the message
            print(f"Error checking message deduplication: {e}")
            return False
    
    async def _mark_message_processed(self, event_id: UUID) -> None:
        """
        Mark message as processed for deduplication.
        
        Args:
            event_id: Event identifier
        """
        if not self.deduplication_enabled or not self.redis_client:
            return
        
        dedup_key = f"{self.deduplication_key_prefix}{str(event_id)}"
        
        try:
            # Set key with TTL
            await self.redis_client.setex(
                dedup_key,
                self.deduplication_ttl_seconds,
                "1"
            )
        except RedisError as e:
            # Log error but don't fail the message
            print(f"Error marking message as processed: {e}")
    
    async def _get_queue_depth(self, topic: str) -> int:
        """
        Get current queue depth for a topic.
        
        Args:
            topic: Topic name
            
        Returns:
            Current queue depth
        """
        if not self.redis_client:
            return 0
        
        queue_key = f"{self.queue_depth_key_prefix}{topic}"
        
        try:
            depth = await self.redis_client.get(queue_key)
            return int(depth) if depth else 0
        except (RedisError, ValueError) as e:
            print(f"Error getting queue depth for topic '{topic}': {e}")
            return 0
    
    async def _increment_queue_depth(self, topic: str) -> int:
        """
        Increment queue depth for a topic.
        
        Args:
            topic: Topic name
            
        Returns:
            New queue depth
        """
        if not self.redis_client:
            return 0
        
        queue_key = f"{self.queue_depth_key_prefix}{topic}"
        
        try:
            # Increment and set expiry (1 hour)
            new_depth = await self.redis_client.incr(queue_key)
            await self.redis_client.expire(queue_key, 3600)
            return new_depth
        except RedisError as e:
            print(f"Error incrementing queue depth for topic '{topic}': {e}")
            return 0
    
    async def _decrement_queue_depth(self, topic: str) -> int:
        """
        Decrement queue depth for a topic.
        
        Args:
            topic: Topic name
            
        Returns:
            New queue depth
        """
        if not self.redis_client:
            return 0
        
        queue_key = f"{self.queue_depth_key_prefix}{topic}"
        
        try:
            new_depth = await self.redis_client.decr(queue_key)
            # Ensure depth doesn't go negative
            if new_depth < 0:
                await self.redis_client.set(queue_key, 0)
                return 0
            return new_depth
        except RedisError as e:
            print(f"Error decrementing queue depth for topic '{topic}': {e}")
            return 0
    
    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """
        Publish event to topic.
        
        Args:
            topic: Topic name (e.g., "data.raw.news")
            payload: Event payload dictionary
            
        Raises:
            EventBusError: If publishing fails or queue is full
        """
        if not self.redis_client:
            raise EventBusError("Event bus not connected")
        
        # Check queue depth for backpressure
        current_depth = await self._get_queue_depth(topic)
        if current_depth >= self.max_queue_depth_per_topic:
            error_msg = f"Queue full for topic '{topic}', please retry later"
            if self.metrics:
                self.metrics.record_error(topic, self._extract_event_type(topic), 'backpressure')
            raise EventBusError(error_msg)
        
        # Create event with metadata
        event = Event(
            event_id=uuid4(),
            event_type=self._extract_event_type(topic),
            topic=topic,
            payload=payload,
            timestamp=datetime.utcnow(),
            schema_version="1.0",
            trace_id=uuid4()
        )
        
        # Check for duplicate message
        if await self._is_duplicate_message(event.event_id):
            # Message already processed, skip publishing
            if self.metrics:
                self.metrics.record_error(topic, event.event_type, 'duplicate')
            print(f"Duplicate message detected: {event.event_id}, skipping publish")
            return
        
        # Serialize event
        try:
            serialized = self.serializer.serialize(event)
        except Exception as e:
            # Record serialization error
            if self.metrics:
                self.metrics.record_error(topic, event.event_type, 'serialization')
            raise EventBusError(f"Failed to serialize event: {e}")
        
        # Publish to Redis
        try:
            await self.redis_client.publish(topic, serialized)
            
            # Increment queue depth
            await self._increment_queue_depth(topic)
            
            # DON'T mark message as processed here - let subscribers do it
            # This prevents the duplicate detection from blocking legitimate subscribers
            
            # Record successful publish
            if self.metrics:
                self.metrics.record_publish(topic, event.event_type)
                
        except RedisError as e:
            # Record connection error
            if self.metrics:
                self.metrics.record_error(topic, event.event_type, 'connection')
            raise EventBusError(f"Failed to publish event to topic '{topic}': {e}")
    
    async def subscribe(self, pattern: str, handler: Callable) -> None:
        """
        Subscribe to topic pattern with handler.
        
        Args:
            pattern: Topic pattern (e.g., "data.raw.*")
            handler: Async function to handle events
        """
        if pattern not in self.subscribers:
            self.subscribers[pattern] = []
        
        self.subscribers[pattern].append(handler)
        
        # Subscribe to pattern in Redis
        if self.pubsub_client:
            await self.pubsub_client.psubscribe(pattern)
            
            # Start subscriber task if not already running
            if not self._subscriber_task or self._subscriber_task.done():
                self._subscriber_task = asyncio.create_task(self._process_messages())
    
    async def unsubscribe(self, pattern: str, handler: Callable) -> None:
        """
        Unsubscribe handler from topic pattern.
        
        Args:
            pattern: Topic pattern
            handler: Handler function to remove
        """
        if pattern in self.subscribers:
            if handler in self.subscribers[pattern]:
                self.subscribers[pattern].remove(handler)
            
            # If no more handlers for this pattern, unsubscribe from Redis
            if not self.subscribers[pattern]:
                del self.subscribers[pattern]
                if self.pubsub_client:
                    await self.pubsub_client.punsubscribe(pattern)
    
    async def _process_messages(self) -> None:
        """Background task to process incoming messages."""
        if not self.pubsub_client:
            return
        
        try:
            async for message in self.pubsub_client.listen():
                if self._shutdown_requested:
                    break
                
                # Skip non-message types
                if message['type'] not in ('pmessage', 'message'):
                    continue
                
                # Increment in-flight counter
                self._in_flight_messages += 1
                if self.metrics:
                    self.metrics.increment_in_flight()
                
                # Track processing start time
                start_time = time.time()
                
                event = None
                try:
                    # Extract data
                    if message['type'] == 'pmessage':
                        pattern = message['pattern'].decode('utf-8')
                        data = message['data']
                    else:
                        pattern = message['channel'].decode('utf-8')
                        data = message['data']
                    
                    # Deserialize event
                    try:
                        event = self.serializer.deserialize(data)
                        
                        # Check for duplicate message on subscriber side
                        if await self._is_duplicate_message(event.event_id):
                            # Message already processed, skip handling
                            if self.metrics:
                                self.metrics.record_error(event.topic, event.event_type, 'duplicate')
                            print(f"Duplicate message detected on subscriber: {event.event_id}, skipping")
                            continue
                        
                        # Mark message as being processed
                        await self._mark_message_processed(event.event_id)
                        
                        # Record message received
                        if self.metrics:
                            self.metrics.record_receive(event.topic, event.event_type)
                            
                    except Exception as e:
                        # Deserialization failed - move to DLQ if enabled
                        error_msg = f"Failed to deserialize event: {e}"
                        print(f"Error: {error_msg}")
                        
                        # Record deserialization error
                        if self.metrics:
                            self.metrics.record_error(pattern, 'unknown', 'deserialization')
                        
                        if self.dlq_enabled and self.dlq:
                            # Try to create a minimal event for DLQ tracking
                            # Since we can't deserialize, we'll log the raw message
                            print(f"Raw message moved to DLQ: {data[:200]}")  # Log first 200 bytes
                        
                        continue
                    
                    # Find matching handlers
                    handlers = self._find_handlers(pattern)
                    
                    # Execute handlers
                    handler_errors = []
                    for handler in handlers:
                        try:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(event)
                            else:
                                handler(event)
                        except Exception as e:
                            # Collect handler errors
                            handler_errors.append(str(e))
                            print(f"Error in event handler: {e}")
                            
                            # Record handler error
                            if self.metrics:
                                self.metrics.record_error(event.topic, event.event_type, 'handler')
                    
                    # If all handlers failed and DLQ is enabled, track the failure
                    if handler_errors and len(handler_errors) == len(handlers) and self.dlq_enabled and self.dlq:
                        error_msg = f"All handlers failed: {'; '.join(handler_errors)}"
                        should_move_to_dlq = await self.dlq.track_failure(event, error_msg)
                        
                        if not should_move_to_dlq:
                            # Event will be retried - log it
                            print(f"Event {event.event_id} will be retried")
                    
                    # Record processing latency (only if successful)
                    if not handler_errors and self.metrics and event:
                        latency = time.time() - start_time
                        self.metrics.record_latency(event.topic, event.event_type, latency)
                
                except Exception as e:
                    print(f"Error processing message: {e}")
                    
                    # Record processing error
                    if self.metrics and event:
                        self.metrics.record_error(event.topic, event.event_type, 'processing')
                    
                    # If we have the event and DLQ is enabled, track the failure
                    if event and self.dlq_enabled and self.dlq:
                        await self.dlq.track_failure(event, str(e))
                
                finally:
                    # Decrement queue depth if we have the event
                    if event:
                        await self._decrement_queue_depth(event.topic)
                    
                    # Decrement in-flight counter
                    self._in_flight_messages -= 1
                    if self.metrics:
                        self.metrics.decrement_in_flight()
                    
                    # Signal if shutdown and no more in-flight messages
                    if self._shutdown_requested and self._in_flight_messages == 0:
                        self._shutdown_event.set()
        
        except asyncio.CancelledError:
            pass
    
    def _find_handlers(self, pattern: str) -> list[Callable]:
        """Find all handlers matching the pattern."""
        handlers = []
        
        for sub_pattern, sub_handlers in self.subscribers.items():
            # Exact match or wildcard match
            if sub_pattern == pattern or self._pattern_matches(sub_pattern, pattern):
                handlers.extend(sub_handlers)
        
        return handlers
    
    def _pattern_matches(self, pattern: str, topic: str) -> bool:
        """Check if pattern matches topic (simple wildcard support)."""
        # Convert Redis pattern to regex-like matching
        # data.raw.* matches data.raw.news, data.raw.market_data, etc.
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return topic.startswith(prefix)
        
        return pattern == topic
    
    def _extract_event_type(self, topic: str) -> str:
        """Extract event type from topic name."""
        # data.raw.news -> data.raw
        # ai.high_value_signal -> ai.high_value_signal
        parts = topic.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[:2])
        return topic
    
    async def graceful_shutdown(self, timeout: int = 30) -> None:
        """
        Gracefully shutdown event bus.
        
        Waits up to timeout seconds for in-flight messages to complete.
        
        Args:
            timeout: Maximum wait time in seconds
        """
        self._shutdown_requested = True
        
        # Wait for in-flight messages with timeout
        if self._in_flight_messages > 0:
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                print(f"Shutdown timeout: {self._in_flight_messages} messages still in-flight")
        
        # Cancel subscriber task
        if self._subscriber_task and not self._subscriber_task.done():
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect
        await self.disconnect()
    
    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            asyncio.create_task(self.graceful_shutdown())
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    def get_dead_letter_queue(self) -> Optional[DeadLetterQueue]:
        """
        Get Dead Letter Queue instance.
        
        Returns:
            DeadLetterQueue instance if enabled, None otherwise
        """
        return self.dlq if self.dlq_enabled else None
    
    def get_metrics(self) -> Optional[EventMetrics]:
        """
        Get EventMetrics instance.
        
        Returns:
            EventMetrics instance if enabled, None otherwise
        """
        return self.metrics if self.metrics_enabled else None
    
    async def get_queue_depth_metrics(self) -> dict[str, int]:
        """
        Get queue depth for all topics.
        
        Returns:
            Dictionary mapping topic names to queue depths
        """
        if not self.redis_client:
            return {}
        
        try:
            # Get all queue depth keys
            pattern = f"{self.queue_depth_key_prefix}*"
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            # Get depths for all keys
            depths = {}
            for key in keys:
                topic = key.decode('utf-8').replace(self.queue_depth_key_prefix, '')
                depth = await self._get_queue_depth(topic)
                depths[topic] = depth
            
            return depths
        except RedisError as e:
            print(f"Error getting queue depth metrics: {e}")
            return {}
