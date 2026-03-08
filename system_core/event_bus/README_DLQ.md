# Dead Letter Queue (DLQ) Implementation

## Overview

The Dead Letter Queue (DLQ) is a critical component of the Event Bus that handles events that fail processing after multiple retry attempts. It uses Redis List data structure for storage and provides comprehensive retry tracking and error logging.

## Features

- **Automatic Retry Tracking**: Tracks retry attempts per event with configurable maximum retries
- **Exponential Backoff**: Implements exponential backoff strategy for retry delays
- **Error Logging**: Logs detailed error information for each failure
- **Event Storage**: Stores failed events in Redis List with configurable retention
- **Size Management**: Automatically trims DLQ to maximum size (keeps most recent events)
- **Cleanup**: Supports manual and automatic cleanup of old events
- **Query Support**: Retrieve failed events for inspection and manual intervention

## Architecture

### Components

1. **FailedEvent**: Represents an event that failed processing
   - Tracks original event, error message, retry count, and timestamps
   - Serializable to/from dictionary for Redis storage

2. **DeadLetterQueue**: Main DLQ implementation
   - Uses Redis List (`RPUSH`/`LRANGE`) for event storage
   - Uses Redis keys with TTL for retry tracking
   - Implements exponential backoff calculation
   - Provides management operations (get, remove, clear, cleanup)

3. **EventBus Integration**: 
   - DLQ is initialized when EventBus connects to Redis
   - Event processing failures are automatically tracked
   - Deserialization failures are logged and moved to DLQ

## Configuration

DLQ is configured through EventBus initialization parameters:

```python
event_bus = EventBus(
    redis_url="redis://localhost:6379",
    dlq_enabled=True,                    # Enable/disable DLQ
    dlq_max_retry_attempts=3,            # Max retries before DLQ
    dlq_retry_delay_seconds=60,          # Initial retry delay
    dlq_retry_backoff_multiplier=2,      # Backoff multiplier
    dlq_retention_days=7,                # How long to keep events
    dlq_max_size=10000                   # Maximum DLQ size
)
```

Or via configuration file (`config/event_bus.yaml`):

```yaml
dead_letter_queue:
  enabled: true
  max_retry_attempts: 3
  retry_delay_seconds: 60
  retry_backoff_multiplier: 2
  retention_days: 7
  max_size: 10000
```

## Usage

### Basic Usage

```python
from system_core.event_bus import EventBus

# Create Event Bus with DLQ
event_bus = EventBus(
    redis_url="redis://localhost:6379",
    dlq_enabled=True,
    dlq_max_retry_attempts=3
)

await event_bus.connect()

# Get DLQ instance
dlq = event_bus.get_dead_letter_queue()

# Check DLQ size
size = await dlq.get_dlq_size()
print(f"DLQ contains {size} failed events")

# Get failed events
failed_events = await dlq.get_failed_events()
for fe in failed_events:
    print(f"Event {fe.event.event_id} failed {fe.retry_count} times")
    print(f"Error: {fe.error}")
```

### Manual Failure Tracking

```python
# Track event failure
should_move_to_dlq = await dlq.track_failure(event, "Error message")

if should_move_to_dlq:
    print("Event moved to DLQ after max retries")
else:
    print("Event will be retried")

# Check retry count
retry_count = await dlq.get_retry_count(event.event_id)
print(f"Current retry count: {retry_count}")
```

### DLQ Management

```python
# Get failed events (with pagination)
recent_failures = await dlq.get_failed_events(start=0, end=9)  # First 10

# Remove specific event
removed = await dlq.remove_event(event_id)

# Cleanup old events
removed_count = await dlq.cleanup_old_events()

# Clear entire DLQ
cleared_count = await dlq.clear_dlq()
```

## Retry Strategy

The DLQ implements exponential backoff for retry delays:

```
Delay = retry_delay_seconds * (retry_backoff_multiplier ^ (retry_count - 1))
```

Example with default settings (60s initial, 2x multiplier):
- Retry 1: 60 seconds
- Retry 2: 120 seconds (60 * 2^1)
- Retry 3: 240 seconds (60 * 2^2)
- Retry 4: 480 seconds (60 * 2^3)

After exceeding `max_retry_attempts`, the event is moved to DLQ.

## Redis Data Structures

### Retry Tracking

Key: `event_bus:retry:{event_id}`
- Type: String (JSON)
- TTL: 2 * calculated retry delay
- Content: FailedEvent serialized to JSON

### Dead Letter Queue

Key: `event_bus:dead_letter_queue`
- Type: List
- Operations: RPUSH (add), LRANGE (get), LREM (remove), LTRIM (size limit)
- TTL: retention_days * 86400 seconds

## Error Handling

### Deserialization Failures

When an event cannot be deserialized:
1. Error is logged with raw message (first 200 bytes)
2. Event cannot be added to DLQ (no event_id available)
3. Processing continues with next event

### Handler Failures

When all handlers fail for an event:
1. Failure is tracked in DLQ
2. Retry count is incremented
3. If max retries exceeded, event moves to DLQ
4. Error details are logged

### Redis Failures

When Redis operations fail:
1. Error is logged
2. Event is NOT moved to DLQ (to avoid data loss)
3. Processing continues

## Monitoring

### Metrics to Track

- DLQ size: `await dlq.get_dlq_size()`
- Retry counts per event: `await dlq.get_retry_count(event_id)`
- Failed events: `await dlq.get_failed_events()`

### Logging

DLQ logs the following events:
- Warning: Event failure with retry count
- Error: Event moved to DLQ after max retries
- Info: Event removed from DLQ
- Info: DLQ cleared
- Info: Old events cleaned up

## Best Practices

1. **Set Appropriate Retry Limits**: Balance between giving events a chance to succeed and not overwhelming the system
   - Transient errors: Higher retry count (5-10)
   - Permanent errors: Lower retry count (2-3)

2. **Monitor DLQ Size**: Set up alerts when DLQ size exceeds threshold
   - Indicates systemic issues with event processing
   - May require manual intervention

3. **Regular Cleanup**: Schedule periodic cleanup of old events
   - Prevents DLQ from growing indefinitely
   - Keeps storage costs manageable

4. **Investigate Failures**: Regularly review failed events
   - Identify patterns in failures
   - Fix underlying issues
   - Consider adjusting retry strategy

5. **Size Limits**: Set appropriate max_size based on expected failure rate
   - Too small: May lose important failure information
   - Too large: Increased storage costs

## Requirements Satisfied

This implementation satisfies the following requirements:

- **Requirement 3.6**: THE Event_Bus SHALL implement Dead_Letter_Queue using Redis List for events that fail processing after 3 retry attempts
- **Requirement 32.6**: WHEN deserialization fails due to invalid JSON, THE Event_Bus SHALL log error with raw message and move event to Dead_Letter_Queue

## Testing

Run unit tests:
```bash
pytest tests/test_dead_letter_queue.py::TestFailedEvent -v
pytest tests/test_dead_letter_queue.py::TestDeadLetterQueueUnit -v
```

Run integration tests (requires Redis):
```bash
pytest tests/test_dead_letter_queue.py -m integration -v
pytest tests/test_event_bus_dlq_integration.py -m integration -v
```

Run example:
```bash
python examples/event_bus_dlq_example.py
```

## Future Enhancements

Potential improvements for future versions:

1. **Automatic Retry**: Implement automatic retry mechanism with scheduled redelivery
2. **DLQ Dashboard**: Web UI for viewing and managing failed events
3. **Alert Integration**: Send notifications when DLQ size exceeds threshold
4. **Event Replay**: Support for replaying failed events after fixing issues
5. **Failure Analysis**: Aggregate failure statistics and patterns
6. **Multiple DLQs**: Support separate DLQs per topic or event type
7. **Dead Letter Exchange**: Support for routing failed events to different handlers
