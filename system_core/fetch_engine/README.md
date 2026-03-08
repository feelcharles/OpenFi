# Fetch Engine Module

## Overview

The Fetch Engine is responsible for orchestrating data acquisition from multiple external sources with scheduling, transformation, error handling, and health monitoring.

## Architecture

```
FetchEngine (Orchestrator)
├── DataFetcher (Abstract Base)
│   ├── EconomicCalendarFetcher
│   ├── MarketDataFetcher
│   ├── NewsAPIFetcher
│   └── SocialMediaFetcher
├── DataTransformer (Quality Scoring)
└── APScheduler (Task Scheduling)
```

## Components

### 1. FetchEngine (Orchestrator)

**Responsibilities:**
- Load and validate data source configurations
- Schedule fetch tasks using APScheduler (cron and interval)
- Maintain registry of active fetchers
- Provide health check endpoint
- Support configuration hot reload

**Key Methods:**
- `load_config()` - Load fetch sources from YAML
- `validate_sources()` - Validate API credentials and schedules
- `schedule_tasks()` - Schedule fetch tasks
- `register_fetcher()` - Register fetcher instances
- `health_check()` - Get health status of all sources
- `reload_config()` - Hot reload configuration

### 2. DataFetcher (Abstract Base Class)

**Responsibilities:**
- Fetch data from external APIs
- Transform to standardized format
- Publish to Event Bus
- Retry with exponential backoff
- Duplicate detection
- Metrics tracking

**Key Methods:**
- `fetch()` - Abstract method to fetch from API
- `transform()` - Abstract method to transform data
- `publish()` - Publish to Event Bus
- `retry_with_backoff()` - Exponential backoff retry
- `is_duplicate()` - Check for duplicates
- `get_metrics()` - Get fetcher metrics

**Retry Strategy:**
- Initial delay: 1 second
- Backoff multiplier: 2x
- Max attempts: 3

**Duplicate Detection:**
- Uses hash of: source + external_id + timestamp
- In-memory cache (can be Redis in production)

### 3. Specific Fetchers

#### EconomicCalendarFetcher
- Fetches economic calendar events
- Supports ForexFactory API
- Data type: `economic_event`
- Topic: `data.raw.economic_calendar`

#### MarketDataFetcher
- Fetches OHLCV market data
- Supports Alpha Vantage API
- Data type: `market_data`
- Topic: `data.raw.market_data`

#### NewsAPIFetcher
- Fetches news articles
- Supports NewsAPI.org
- Data type: `news`
- Topic: `data.raw.news`

#### SocialMediaFetcher
- Fetches social media posts
- Supports Twitter/X API v2
- Data type: `social_post`
- Topic: `data.raw.social_media`

### 4. DataTransformer

**Responsibilities:**
- Extract relevant fields
- Normalize data types
- Validate required fields
- Calculate quality scores
- Enrich metadata

**Quality Score Calculation (0-100):**
- Completeness (40%): Percentage of non-null fields
- Freshness (40%): Age of data
- Consistency (20%): Data format consistency

**Normalization:**
- Timestamps → ISO 8601 format
- Prices → Decimal strings
- Symbols → Uppercase
- Nested dictionaries → Recursive normalization

## Configuration

### fetch_sources.yaml

```yaml
sources:
  - source_id: "forexfactory_calendar"
    source_type: "economic_calendar"
    api_endpoint: "https://api.forexfactory.com/calendar"
    credentials:
      api_key: "${FOREXFACTORY_API_KEY}"
    schedule_type: "cron"
    schedule_config:
      cron: "0 */6 * * *"  # Every 6 hours
    enabled: true
    retry_count: 3
    timeout: 30
```

**Schedule Types:**
- `cron`: Cron expression (e.g., "0 */6 * * *")
- `interval`: Fixed interval in seconds (e.g., 300)

## Data Flow

1. **Scheduling**: FetchEngine schedules tasks based on configuration
2. **Execution**: APScheduler triggers fetch tasks
3. **Fetching**: DataFetcher fetches from external API with retry
4. **Transformation**: DataTransformer normalizes and validates data
5. **Quality Check**: Calculate quality score, discard if < 50
6. **Duplicate Check**: Check if data already seen
7. **Publishing**: Publish to Event Bus topic `data.raw.{source_type}`

## Event Bus Topics

- `data.raw.economic_calendar` - Economic calendar events
- `data.raw.market_data` - Market price data
- `data.raw.news` - News articles
- `data.raw.social_media` - Social media posts
- `data.raw.academic_paper` - Academic papers

## Health Monitoring

Health status includes:
- `status`: "healthy" | "unhealthy" | "scheduled"
- `last_fetch_time`: ISO timestamp
- `last_success_time`: ISO timestamp
- `last_error`: Error message (if any)
- `success_count`: Total successful fetches
- `failure_count`: Total failed fetches

## Metrics

Per-fetcher metrics:
- `total_requests`: Total API requests
- `successful_fetches`: Successful fetches
- `failed_fetches`: Failed fetches
- `duplicate_count`: Duplicates detected
- `average_response_time`: Average response time (seconds)

## Error Handling

**4xx/5xx Errors:**
- Log full request and response details
- Retry with exponential backoff
- Update health status

**Network Errors:**
- Retry with exponential backoff
- Log error with trace_id

**Low Quality Data:**
- Log warning if quality_score < 50
- Optionally discard data

## Structured Logging

All operations logged with:
- `timestamp`: ISO 8601 timestamp
- `level`: DEBUG | INFO | WARNING | ERROR
- `module`: "fetch_engine"
- `function`: Function name
- `trace_id`: UUID for correlation
- `source_id`: Source identifier
- `context`: Additional context

## Usage Example

```python
from system_core.fetch_engine import FetchEngine
from system_core.config import ConfigurationManager
from system_core.event_bus import EventBus

# Initialize
config_manager = ConfigurationManager()
event_bus = EventBus(redis_url="redis://localhost:6379")
fetch_engine = FetchEngine(config_manager, event_bus)

# Load and validate
config = await fetch_engine.load_config()
fetch_engine.validate_sources(config)

# Register fetchers
for source in config["sources"]:
    fetcher = create_fetcher(source, event_bus)
    fetch_engine.register_fetcher(source["source_id"], fetcher)

# Start
await fetch_engine.start()

# Health check
health = fetch_engine.health_check()
print(health)

# Stop
await fetch_engine.stop()
```

## Testing

Run tests:
```bash
pytest tests/test_fetch_engine.py -v
```

Test coverage:
- FetchEngine orchestrator
- DataFetcher base class
- DataTransformer
- Specific fetcher implementations
- Retry logic
- Duplicate detection
- Quality scoring

## Requirements Validation

**Task 6: Fetch Engine Core**
- ✓ 6.1: FetchEngine orchestrator class
- ✓ 6.2: Task scheduling (cron and interval)
- ✓ 6.3: Health check endpoint
- ✓ 6.4: Structured logging

**Task 7: Data Fetcher Implementations**
- ✓ 7.1: Abstract DataFetcher base class
- ✓ 7.4: EconomicCalendarFetcher
- ✓ 7.5: MarketDataFetcher
- ✓ 7.6: NewsAPIFetcher
- ✓ 7.7: SocialMediaFetcher
- ✓ 7.8: Error handling and metrics

**Task 8: Data Transformation Pipeline**
- ✓ 8.1: DataTransformer class
- ✓ 8.2: Data quality scoring

**Requirements:**
- ✓ 1.1: Load configurations from YAML
- ✓ 1.2: Validate configurations
- ✓ 1.3: Cron-based scheduling
- ✓ 1.4: Interval-based scheduling
- ✓ 1.5: Fetcher registry
- ✓ 1.6: Health check endpoint
- ✓ 1.7: Configuration hot reload
- ✓ 1.8: Structured logging
- ✓ 2.1-2.8: Multi-source data fetching
- ✓ 23.2-23.7: Data transformation and quality

## Future Enhancements

1. **Redis-based duplicate detection** - Replace in-memory cache
2. **Rate limiting** - Per-source rate limits
3. **Backpressure handling** - Queue depth limits
4. **Metrics export** - Prometheus metrics
5. **Academic paper fetchers** - arXiv, SSRN, Google Scholar
6. **Webhook support** - Push-based data sources
7. **Data validation schemas** - JSON Schema validation
8. **Retry policies** - Configurable retry strategies
