# Idempotency and Duplicate Prevention

This document describes the idempotency and duplicate prevention mechanisms implemented in OpenFi Lite.

## Overview

The system implements two complementary mechanisms for preventing duplicate operations:

1. **API Idempotency**: Prevents duplicate API requests using idempotency keys
2. **Event Bus Deduplication**: Prevents duplicate event processing using message IDs

**Validates: Requirements 37.1, 37.2, 37.3, 37.4, 37.7**

## API Idempotency

### How It Works

The `IdempotencyMiddleware` provides idempotency support for API endpoints:

1. **Client sends request** with optional `Idempotency-Key` header
2. **Middleware checks Redis** for cached response using key + request hash
3. **If cached response exists**, return it immediately (with `X-Idempotency-Cached: true` header)
4. **If no cached response**, process request normally and cache the response
5. **Response cached for 24 hours** (configurable TTL)

### Supported Methods

Idempotency checking is applied to:
- POST requests
- PUT requests  
- DELETE requests

GET requests are naturally idempotent and don't require special handling.

### Request Hash

To ensure the same idempotency key with different request bodies doesn't return incorrect cached responses, the middleware generates a hash of:
- HTTP method
- Request path
- Query parameters
- Request body

The Redis key format is: `idempotency:{idempotency_key}:{request_hash}`

### Usage Example

```python
import requests

# First request with idempotency key
response1 = requests.post(
    "http://localhost:8000/api/users",
    json={"name": "John", "email": "john@example.com"},
    headers={"Idempotency-Key": "create-user-123"}
)
# Response: 201 Created, user created

# Duplicate request with same idempotency key
response2 = requests.post(
    "http://localhost:8000/api/users",
    json={"name": "John", "email": "john@example.com"},
    headers={"Idempotency-Key": "create-user-123"}
)
# Response: 201 Created, cached response returned
# Header: X-Idempotency-Cached: true
# User NOT created again
```

### Configuration

The middleware is configured in `system_core/web_backend/app.py`:

```python
idempotency_handler = IdempotencyMiddleware(
    redis_url=settings.redis_url,
    password=settings.redis_password,
    ttl_seconds=86400  # 24 hours
)
```

## Event Bus Message Deduplication

### How It Works

The Event Bus implements at-least-once delivery with deduplication:

1. **Publisher generates unique event_id** (UUID) for each event
2. **Before publishing**, check if event_id already exists in Redis
3. **If duplicate**, skip publishing and log warning
4. **If not duplicate**, publish event and mark event_id as processed
5. **Subscriber receives event**, checks for duplicate before processing
6. **If duplicate on subscriber side**, skip processing
7. **Event IDs tracked for 1 hour** (configurable TTL)

### Deduplication Tracking

Event IDs are stored in Redis with format: `event_dedup:{event_id}`

The TTL ensures old event IDs are automatically cleaned up, preventing unbounded memory growth.

### Usage Example

```python
from system_core.event_bus import EventBus

# Initialize Event Bus with deduplication enabled
event_bus = EventBus(
    redis_url="redis://localhost:6379/0",
    deduplication_enabled=True,
    deduplication_ttl_seconds=3600  # 1 hour
)
await event_bus.connect()

# Publish event
payload = {"data": "important message"}
await event_bus.publish("test.topic", payload)

# If the same event_id is published again (e.g., due to retry),
# it will be automatically deduplicated
```

### At-Least-Once Delivery Guarantee

The deduplication mechanism ensures:
- **At-least-once delivery**: Events are delivered at least once to subscribers
- **No duplicate processing**: Even if an event is delivered multiple times (due to network issues, retries, etc.), it's only processed once
- **Idempotent operations**: Combined with idempotent handlers, ensures system consistency

## Implementation Details

### Files

- `system_core/core/idempotency.py` - Idempotency middleware implementation
- `system_core/event_bus/event_bus.py` - Event Bus with deduplication
- `system_core/web_backend/app.py` - Middleware integration
- `tests/test_idempotency.py` - Test suite

### Redis Keys

**Idempotency Keys:**
```
idempotency:{idempotency_key}:{request_hash}
TTL: 24 hours (86400 seconds)
Value: JSON with status_code, body, headers
```

**Event Deduplication Keys:**
```
event_dedup:{event_id}
TTL: 1 hour (3600 seconds)
Value: "1" (presence indicates processed)
```

### Error Handling

Both mechanisms are designed to fail gracefully:
- **Redis connection errors**: Logged but don't block requests/events
- **Serialization errors**: Logged and tracked in metrics
- **Cache misses**: Requests processed normally

### Metrics

The Event Bus tracks deduplication metrics:
- `duplicate` error type in metrics for deduplicated messages
- Prometheus metrics exposed at `/metrics` endpoint

## Testing

### Unit Tests

Run the test suite:
```bash
pytest tests/test_idempotency.py -v
```

**Note:** Tests require Redis to be running on `localhost:6379`

### Manual Testing

1. **Test API Idempotency:**
```bash
# First request
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-123" \
  -d '{"name": "Test User", "email": "test@example.com"}'

# Duplicate request (should return cached response)
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-123" \
  -d '{"name": "Test User", "email": "test@example.com"}'
```

2. **Test Event Bus Deduplication:**
```python
# See examples/event_bus_deduplication_example.py
```

## Best Practices

### For API Clients

1. **Generate unique idempotency keys** for each logical operation
2. **Use UUIDs or timestamps** to ensure uniqueness
3. **Retry with same key** if request fails due to network issues
4. **Don't reuse keys** for different operations

### For Event Publishers

1. **Use unique event_id** for each event (automatically handled by Event Bus)
2. **Don't manually set event_id** unless you have a specific reason
3. **Enable deduplication** in production environments
4. **Monitor duplicate metrics** to detect retry storms

### For Event Subscribers

1. **Design idempotent handlers** that can safely process the same event multiple times
2. **Use database transactions** to ensure atomic operations
3. **Check for duplicates** at the application level if needed (e.g., unique constraints)

## Configuration

### Environment Variables

```bash
# Redis connection for idempotency and deduplication
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your-password-here
```

### Settings

```python
# In system_core/config/settings.py
redis_url: str = Field(default="redis://localhost:6379/0")
redis_password: Optional[str] = Field(default=None)
```

## Troubleshooting

### Issue: Cached responses not being returned

**Possible causes:**
1. Redis not running or not accessible
2. Different request body with same idempotency key
3. TTL expired (24 hours)

**Solution:**
- Check Redis connection
- Verify request body is identical
- Check Redis logs for key expiration

### Issue: Events being processed multiple times

**Possible causes:**
1. Deduplication disabled
2. Redis connection issues
3. Event handlers not idempotent

**Solution:**
- Enable deduplication: `deduplication_enabled=True`
- Check Redis connectivity
- Make handlers idempotent

### Issue: High memory usage in Redis

**Possible causes:**
1. TTL too long
2. High request/event volume
3. Keys not expiring

**Solution:**
- Reduce TTL if appropriate
- Monitor Redis memory usage
- Check Redis eviction policy

## Performance Considerations

### Redis Load

Each idempotent request adds:
- 1 GET operation (check cache)
- 1 SETEX operation (store response)

Each event adds:
- 1 EXISTS operation (check duplicate)
- 1 SETEX operation (mark processed)

### Latency Impact

- **API requests**: ~1-2ms overhead for Redis operations
- **Event processing**: ~1-2ms overhead for Redis operations

### Scalability

- **Redis capacity**: Can handle millions of keys
- **TTL cleanup**: Automatic, no manual intervention needed
- **Horizontal scaling**: Use Redis Cluster for high throughput

## Future Enhancements

Potential improvements:
1. **Distributed locking** for concurrent requests with same idempotency key
2. **Configurable TTL per endpoint** for different caching needs
3. **Metrics dashboard** for idempotency hit rates
4. **Automatic key cleanup** for expired idempotency keys
5. **Support for custom hash functions** for request deduplication
