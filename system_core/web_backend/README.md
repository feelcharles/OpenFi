# Web Backend Module

The Web Backend module provides REST APIs and WebSocket endpoints for the OpenFi Lite web dashboard.

## Features

### REST API Endpoints

#### Dashboard Metrics (`GET /api/dashboard/metrics`)
Returns real-time system metrics:
- Active data sources
- Fetch success rate
- AI processing queue depth
- Active positions
- Account balance
- Signals today
- High-value signals today
- Trades today
- Win rate today

#### System Status (`GET /api/dashboard/system-status`)
Returns system health status:
- Overall status (healthy/degraded/unhealthy)
- System uptime
- Application version
- Component statuses (database, redis, event_bus, etc.)

#### Recent Signals (`GET /api/dashboard/recent-signals`)
Returns recent high-value signals with auto-refresh support (every 10 seconds recommended).

#### Trading History (`GET /api/trades`)
Returns trading history with filters:
- `start_date`: Filter from date
- `end_date`: Filter to date
- `symbol`: Filter by trading symbol
- `limit`: Maximum results (default 50, max 500)

#### Individual Trade (`GET /api/trades/{trade_id}`)
Returns detailed information for a specific trade.

#### Configuration Management
- `GET /api/config/{file_name}`: Load configuration file
- `PUT /api/config/{file_name}`: Save configuration file with validation

### WebSocket Endpoint

#### Real-time Notifications (`WS /ws/notifications`)
WebSocket endpoint for real-time updates:
- High-value signals (`ai.high_value_signal`)
- Executed trades (`trading.executed`)
- System health events (`system.health.*`)

**Message Format:**
```json
{
  "type": "signal" | "trade" | "system_event",
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    // Event-specific data
  }
}
```

**Client Messages:**
- `{"type": "ping"}`: Keepalive ping (server responds with pong)

### Middleware

#### Rate Limiting
- Limit: 100 requests per minute per user
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- WebSocket: 1000 messages per minute per connection

#### CORS
Configured to allow requests from:
- `http://localhost:3000`
- `http://localhost:8080`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:8080`

Additional origins can be configured via `setup_cors()`.

## Usage

### Initialize FastAPI Application

```python
from fastapi import FastAPI
from system_core.web_backend import (
    web_api_router,
    websocket_router,
    RateLimitMiddleware,
    setup_cors,
    event_broadcaster
)
from system_core.event_bus import EventBus

app = FastAPI()

# Setup CORS
setup_cors(app)

# Add rate limiting
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)

# Include routers
app.include_router(web_api_router)
app.include_router(websocket_router)

# Initialize event broadcaster
event_bus = EventBus()
event_broadcaster.set_event_bus(event_bus)

@app.on_event("startup")
async def startup():
    await event_broadcaster.start()

@app.on_event("shutdown")
async def shutdown():
    await event_broadcaster.stop()
```

### WebSocket Client Example (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/notifications');

ws.onopen = () => {
  console.log('Connected to WebSocket');
  
  // Send keepalive ping every 30 seconds
  setInterval(() => {
    ws.send(JSON.stringify({ type: 'ping' }));
  }, 30000);
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch (message.type) {
    case 'signal':
      console.log('New signal:', message.data);
      break;
    case 'trade':
      console.log('Trade executed:', message.data);
      break;
    case 'system_event':
      console.log('System event:', message.data);
      break;
    case 'pong':
      console.log('Keepalive pong received');
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket disconnected');
};
```

## Error Handling

All API endpoints return consistent error responses:

```json
{
  "error": "ErrorType",
  "message": "Human-readable error message",
  "details": {
    // Additional error details
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

Common HTTP status codes:
- `200`: Success
- `400`: Bad request (validation error)
- `401`: Unauthorized
- `404`: Not found
- `429`: Rate limit exceeded
- `500`: Internal server error

## Security

- JWT authentication required for all endpoints (except `/health`)
- Rate limiting to prevent abuse
- CORS configured with whitelist
- Input validation and sanitization
- Configuration file access restricted to allowed files

## Requirements Mapping

- **Requirements 20.2, 21.1**: Dashboard metrics and system status endpoints
- **Requirements 20.4, 21.4, 21.5**: Configuration management endpoints
- **Requirements 20.5, 21.3**: Trading history endpoints
- **Requirements 20.6, 21.1**: Recent signals endpoint
- **Requirements 21.2**: WebSocket server and real-time broadcasting
- **Requirements 21.6**: Rate limiting (API and WebSocket)
- **Requirements 21.7**: CORS configuration
- **Requirements 21.8**: Consistent error responses
