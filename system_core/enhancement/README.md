# Enhancement Module

The Enhancement Module provides advanced features for OpenFi Lite including vector database integration and external tool management.

## Features

### 1. Vector Database Integration

Store and search text embeddings for semantic similarity matching.

**Components:**
- `VectorDB`: Abstract interface for vector databases
- `PineconeDB`: Pinecone adapter implementation
- `EmbeddingService`: OpenAI embedding generation
- `EnhancementModule`: Main orchestrator

**Features:**
- Automatic storage of AI-analyzed information
- Semantic search for historical context (top 5 similar items, <500ms)
- Automatic cleanup of old vectors (daily at 03:00 UTC, >90 days)
- Metrics tracking (total vectors, search queries, latency)

**Configuration:**
```yaml
# config/vector_db.yaml
provider: pinecone
api_key: "${PINECONE_API_KEY}"
environment: "${PINECONE_ENVIRONMENT}"
index_name: OpenFi-vectors
dimension: 1536
metric: cosine

embedding:
  provider: openai
  model: text-embedding-3-small
  batch_size: 100

cleanup:
  enabled: true
  schedule: "0 3 * * *"
  retention_days: 90
```

**Usage:**
```python
from system_core.enhancement import EnhancementModule

# Initialize
enhancement = EnhancementModule(
    config_path="config/vector_db.yaml",
    event_bus=event_bus,
    redis_client=redis_client
)

# Start (subscribes to ai.analyzed events)
await enhancement.start()

# Semantic search
results = await enhancement.semantic_search(
    query_text="interest rate policy",
    top_k=5
)

# Get metrics
metrics = await enhancement.get_metrics()
```

### 2. External Tool Integration

Dynamically register and execute third-party analysis tools.

**Components:**
- `ExternalToolRegistry`: Tool registration and management
- `ExternalTool`: Tool configuration model

**Features:**
- GitHub repository cloning
- Local tool path validation
- File extension whitelist (.py, .js, .sh)
- Suspicious pattern scanning (eval, exec, system calls)
- Two integration methods:
  - `import`: Load as Python module
  - `command_line`: Execute via subprocess
- Risk warnings before execution
- Timeout enforcement (60s default, 120s max)

**Configuration:**
```yaml
# config/external_tools.yaml
tools:
  - name: "technical_analyzer"
    source_type: "github"
    source_url: "https://github.com/example/ta-tool.git"
    integration_method: "import"
    entry_point: "ta_tool.analyze"
    risk_warning: "This tool performs technical analysis"
    timeout: 30
    enabled: false

security:
  allowed_file_extensions: [".py", ".sh", ".js"]
  blocked_patterns:
    - "rm -rf"
    - "eval("
    - "exec("
  max_tool_execution_time: 120
```

**Usage:**
```python
from system_core.enhancement import ExternalToolRegistry

# Initialize
registry = ExternalToolRegistry(config_path="config/external_tools.yaml")

# Download and validate tool
success = registry.download_and_validate_tool("technical_analyzer")

# Execute tool
result = registry.execute_tool(
    tool_name="technical_analyzer",
    params={"symbol": "EURUSD", "timeframe": "H1"}
)

# List tools
tools = registry.list_tools(enabled_only=True)
```

**API Endpoints:**
```
POST /api/tools/{tool_name}/execute - Execute tool
GET  /api/tools                      - List all tools
GET  /api/tools/{tool_name}          - Get tool details
```

### 3. EA Testing Framework

Test Expert Advisors in simulation environment.

**Features:**
- Platform-specific testing:
  - MT4/MT5: Syntax validation, structure checks
  - TradingView: Pine Script validation
- Test result logging to `ea/logs/`
- Error and warning capture
- Execution time tracking
- Test summary with status, error count, log path

**Usage:**
```python
from system_core.execution_engine.ea_manager import EAManager

# Initialize
ea_manager = EAManager(ea_folder="ea", config_path="config/ea_config.yaml")

# Refresh EA list
result = ea_manager.refresh_ea_list()

# Test EA
test_result = ea_manager.test_ea("my_strategy")

# Results
print(f"Status: {test_result['test_status']}")
print(f"Errors: {test_result['error_count']}")
print(f"Log: {test_result['log_file_path']}")
```

## Installation

### Dependencies

```bash
# Vector Database
pip install pinecone-client openai

# External Tools (optional)
pip install gitpython

# Core dependencies (already installed)
pip install pydantic pyyaml redis
```

### Environment Variables

```bash
# Vector Database
export PINECONE_API_KEY="your-api-key"
export PINECONE_ENVIRONMENT="your-environment"
export OPENAI_API_KEY="your-openai-key"
```

## Architecture

```
enhancement/
├── __init__.py                 # Module exports
├── vector_db.py                # Vector DB interface and Pinecone adapter
├── embedding_service.py        # OpenAI embedding generation
├── enhancement_module.py       # Main orchestrator
├── external_tools.py           # Tool registry and execution
├── tools_api.py                # FastAPI endpoints for tools
└── README.md                   # This file
```

## Event Flow

### Vector Storage Pipeline

1. AI Processing Engine publishes to `ai.analyzed` topic
2. Enhancement Module subscribes and receives event
3. Extract text content from event payload
4. Generate embedding using OpenAI
5. Store vector with metadata in Pinecone
6. Update metrics

### Semantic Search

1. AI Processing Engine needs historical context
2. Call `enhancement.semantic_search(query_text)`
3. Generate query embedding
4. Search Pinecone for top K similar vectors
5. Return results with metadata
6. AI includes context in LLM prompt

### Cleanup Job

1. Runs daily at 03:00 UTC
2. Calculate cutoff date (now - retention_days)
3. Delete vectors with timestamp < cutoff
4. Log deleted count

## Metrics

The Enhancement Module tracks:

- `total_vectors_stored`: Total vectors inserted
- `search_queries_per_day`: Daily search count (resets daily)
- `total_search_queries`: Lifetime search count
- `avg_search_latency_ms`: Average search latency
- `storage_size_mb`: Estimated storage size

Access via:
```python
metrics = await enhancement.get_metrics()
```

## Security

### External Tools

- File extension whitelist enforcement
- Suspicious pattern scanning
- Execution timeout limits
- Risk warnings logged before execution
- Sandbox mode support (configurable)

### Vector Database

- API key authentication
- Encrypted connections (TLS)
- Metadata filtering for access control
- Automatic cleanup of old data

## Testing

Run the example:
```bash
python examples/enhancement_module_example.py
```

Run tests:
```bash
pytest tests/test_enhancement.py
```

## Troubleshooting

### Vector DB Connection Issues

```python
# Check Pinecone connection
import pinecone
pinecone.init(api_key="...", environment="...")
print(pinecone.list_indexes())
```

### Embedding Generation Fails

- Verify OPENAI_API_KEY is set
- Check API quota and rate limits
- Ensure text is not empty

### External Tool Execution Fails

- Check tool is enabled in config
- Verify file paths exist
- Review security scan results in logs
- Check timeout settings

## Performance

- Vector search: <500ms for top 5 results
- Embedding generation: ~100ms per text (cached)
- Batch embedding: ~1s per 100 texts
- Tool execution: Varies by tool (60s default timeout)

## Future Enhancements

- Support for Weaviate and Qdrant vector databases
- Advanced tool sandboxing with Docker
- Real-time MT4/MT5 Strategy Tester integration
- Distributed vector search for large datasets
- Tool marketplace and sharing
