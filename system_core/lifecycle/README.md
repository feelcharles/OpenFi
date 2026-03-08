# Lifecycle Module

This module provides application lifecycle management capabilities for OpenFi Lite.

## Features

### 1. Graceful Shutdown

Handles shutdown signals and coordinates graceful cleanup:

```python
from system_core.lifecycle import get_shutdown_manager, register_shutdown_handler

# Get shutdown manager
shutdown_manager = get_shutdown_manager()

# Setup signal handlers (SIGTERM, SIGINT)
shutdown_manager.setup_signal_handlers()

# Register shutdown handlers
async def cleanup_event_bus():
    await event_bus.graceful_shutdown()

register_shutdown_handler(
    name="event_bus",
    handler=cleanup_event_bus,
    priority=100,  # Higher priority runs first
    timeout=30.0   # Max 30 seconds
)

# Wait for shutdown signal
await shutdown_manager.wait_for_shutdown()
```

**Shutdown Sequence:**
1. Stop accepting new requests immediately
2. Execute handlers in priority order (highest first)
3. Wait up to 30 seconds for in-flight messages
4. Close database connections and flush pending writes
5. Close external API connections

### 2. State Persistence and Recovery

Save and restore application state:

```python
from system_core.lifecycle import get_state_manager

state_manager = get_state_manager()

# Save state before shutdown
await state_manager.save_fetch_engine_state({
    "active_tasks": ["task-1", "task-2"]
})

await state_manager.save_circuit_breaker_state({
    "ea-profile-1": {"is_active": True, "failure_count": 3}
})

# Restore state on startup
active_tasks = await state_manager.load_fetch_engine_state()
circuit_breakers = await state_manager.load_circuit_breaker_state()
```

**State File:**
- Location: `state/application_state.json`
- Format: JSON with timestamp and version
- Components: fetch_engine, pending_signals, circuit_breakers

### 3. Health Probes

Kubernetes-compatible health probes:

```python
from system_core.lifecycle import get_readiness_probe, get_liveness_probe

# Readiness probe - ready to accept traffic
readiness = get_readiness_probe()

def check_database_ready():
    return db.is_connected()

readiness.register_check("database", check_database_ready)

# Check readiness
result = await readiness.check()
# Returns: {"ready": True, "timestamp": "...", "checks": {...}}

# Liveness probe - still running
liveness = get_liveness_probe()

# Record heartbeat periodically
liveness.heartbeat()

# Check liveness
result = await liveness.check()
# Returns: {"alive": True, "uptime_seconds": 3600, ...}
```

**Probe Endpoints:**
- `GET /readiness` - Returns 200 if ready, 503 if not
- `GET /liveness` - Returns 200 if alive, 503 if not

### 4. Data Retention and Cleanup

Automated data cleanup based on retention policies:

```python
from system_core.lifecycle import CleanupJob

# Create cleanup job
cleanup_job = CleanupJob(db_session)

# Start scheduled cleanup (daily at 03:00 UTC)
cleanup_job.start_scheduled_cleanup()

# Manual cleanup trigger
result = await cleanup_job.run_cleanup()

# Returns:
# {
#   "start_time": "...",
#   "end_time": "...",
#   "duration_seconds": 45.2,
#   "total_records_deleted": 1500,
#   "total_records_archived": 1500,
#   "total_storage_freed_mb": 25.3,
#   "results": [...]
# }
```

**Retention Policies:**
- `raw_data`: 30 days
- `analyzed_signals`: 90 days
- `trade_records`: 365 days (soft delete)
- `logs`: 30 days
- `notifications`: 60 days

**Features:**
- Archive before delete (compressed gzip)
- Soft delete for critical records
- Batch processing (1000 records at a time)
- Configurable via `config/retention_policy.yaml`

## Configuration

### Retention Policy (`config/retention_policy.yaml`)

```yaml
policies:
  - data_type: analyzed_signals
    retention_days: 90
    archive_before_delete: true
    archive_format: gzip
    description: "Signals analyzed by AI engine"

cleanup_schedule:
  cron: "0 3 * * *"  # Daily at 03:00 UTC
  enabled: true
  batch_size: 1000
  max_execution_time: 3600

archive:
  base_directory: "archive"
  compression_level: 6
  verify_integrity: true
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/readiness` | GET | Readiness probe |
| `/liveness` | GET | Liveness probe |
| `/api/admin/cleanup/run` | POST | Manual cleanup trigger |

## Usage in Application

```python
from system_core.lifecycle import (
    get_shutdown_manager,
    get_state_manager,
    get_readiness_probe,
    get_liveness_probe,
    CleanupJob
)

async def startup():
    # Setup shutdown handling
    shutdown_manager = get_shutdown_manager()
    shutdown_manager.setup_signal_handlers()
    
    # Register shutdown handlers
    register_shutdown_handler("event_bus", cleanup_event_bus, priority=100)
    register_shutdown_handler("database", cleanup_database, priority=90)
    
    # Restore state
    state_manager = get_state_manager()
    active_tasks = await state_manager.load_fetch_engine_state()
    
    # Setup readiness checks
    readiness = get_readiness_probe()
    readiness.register_check("database", check_database)
    readiness.register_check("redis", check_redis)
    
    # Start cleanup job
    cleanup_job = CleanupJob(db)
    cleanup_job.start_scheduled_cleanup()
    
    # Start heartbeat for liveness
    liveness = get_liveness_probe()
    asyncio.create_task(heartbeat_loop(liveness))

async def heartbeat_loop(liveness):
    while True:
        liveness.heartbeat()
        await asyncio.sleep(30)

async def shutdown():
    # Save state
    state_manager = get_state_manager()
    await state_manager.save_fetch_engine_state(active_tasks)
    
    # Trigger shutdown
    shutdown_manager = get_shutdown_manager()
    await shutdown_manager.shutdown()
```

## Requirements Validation

This module validates the following requirements:
- **28.1-28.8**: Graceful shutdown, state persistence, health probes
- **29.1-29.7**: Data retention, cleanup, archiving
