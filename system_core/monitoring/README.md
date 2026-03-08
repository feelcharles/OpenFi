# Monitoring Module

This module provides comprehensive monitoring and observability capabilities for OpenFi Lite.

## Features

### 1. Structured Logging with Trace ID

Enhanced logging system with distributed tracing support:

```python
from system_core.monitoring import setup_logging_with_trace_id, get_logger, set_trace_id

# Setup logging at application startup
setup_logging_with_trace_id(
    log_level="INFO",
    log_file_path="logs/OpenFi.log",
    log_max_bytes=104857600,  # 100MB
    log_backup_count=10
)

# Get logger instance
logger = get_logger(__name__)

# Set trace ID for request context
set_trace_id("request-123")

# Log with automatic trace_id inclusion
logger.info("processing_started", user_id="user-1", action="fetch")
```

**Log Format:**
- **Console (stdout)**: Human-readable format for containers
- **File (JSON)**: Structured JSON format with fields:
  - `timestamp`: ISO 8601 format
  - `level`: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - `module`: Logger name
  - `function`: Function name
  - `message`: Log message
  - `trace_id`: Distributed tracing ID
  - Additional context fields

### 2. Prometheus Metrics

Comprehensive metrics collection for monitoring:

```python
from system_core.monitoring import get_metrics_collector

metrics = get_metrics_collector()

# Counter metrics
metrics.increment_fetch_requests("news_api", status="success")
metrics.increment_llm_calls("openai", "gpt-4", status="success")
metrics.increment_trades_executed("EURUSD", "long", status="success")

# Gauge metrics
metrics.set_active_fetch_tasks("news_api", 5)
metrics.set_event_bus_queue_depth("ai.high_value_signal", 10)
metrics.set_account_balance("account-1", "USD", 10000.0)

# Histogram metrics
metrics.observe_fetch_duration("news_api", 2.5)
metrics.observe_llm_response_time("openai", "gpt-4", 3.2)

# Business KPI metrics
metrics.set_signals_per_hour(15.5)
metrics.set_high_value_signal_rate(35.0)
metrics.set_trade_win_rate("my-ea", 65.0)
```

**Metrics Endpoint:**
- `GET /metrics` - Prometheus exposition format

### 3. Health Checks

Component health monitoring:

```python
from system_core.monitoring import get_health_checker, register_health_check

# Register component health checks
def check_database():
    # Return True if healthy, False otherwise
    return db.is_connected()

register_health_check("database", check_database)

# Get health report
health_checker = get_health_checker()
report = await health_checker.get_health_report(version="1.0.0")
```

**Health Endpoint:**
- `GET /health` - Overall system health with component statuses

### 4. Error Recovery Strategies

Resilient error handling:

```python
from system_core.monitoring import retry_with_backoff, with_retry, FallbackHandler

# Retry with exponential backoff
result = await retry_with_backoff(
    fetch_data,
    max_attempts=3,
    initial_delay=1.0,
    backoff_multiplier=2.0
)

# Decorator for retry
@with_retry(max_attempts=3, initial_delay=1.0)
async def fetch_data():
    # ... code that might fail transiently
    pass

# Fallback handler
handler = FallbackHandler(
    primary=call_openai,
    fallback=call_anthropic,
    name="llm_service"
)
result = await handler.execute(prompt)
```

### 5. Metrics Aggregation

Business intelligence metrics:

```python
from system_core.monitoring import MetricsAggregator

aggregator = MetricsAggregator(db_session)
summary = await aggregator.get_summary(period="24h")

# Returns:
# - Signal metrics (total, high-value, rates)
# - Trade metrics (total, win rate, profit)
# - Notification metrics (total, success rate)
```

**Aggregation Endpoint:**
- `GET /api/metrics/summary?period={1h|24h|7d|30d}` - Aggregated metrics

## Configuration

Logging is configured at application startup. Metrics are automatically collected when using the monitoring decorators and explicit metric calls.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health check |
| `/metrics` | GET | Prometheus metrics |
| `/api/metrics/summary` | GET | Aggregated metrics summary |
| `/readiness` | GET | Readiness probe |
| `/liveness` | GET | Liveness probe |

## Requirements Validation

This module validates the following requirements:
- **24.1-24.8**: Structured logging, error handling, health checks
- **25.1-25.8**: Prometheus metrics, business KPIs, aggregation
