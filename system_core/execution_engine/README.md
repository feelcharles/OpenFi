# Execution Engine Module

The Execution Engine is responsible for generating trading signals based on AI analysis and EA (Expert Advisor) configurations. It orchestrates the flow from high-value signals to actionable trading recommendations.

## Architecture

```
┌─────────────────────┐
│  AI Processing      │
│  Engine             │
└──────────┬──────────┘
           │ publishes
           │ ai.high_value_signal
           ▼
┌─────────────────────┐
│  Event Bus          │
│  (Redis Pub/Sub)    │
└──────────┬──────────┘
           │ subscribes
           ▼
┌─────────────────────┐
│  Execution Engine   │
│  ┌───────────────┐  │
│  │ Match EA      │  │
│  │ Profiles      │  │
│  └───────┬───────┘  │
│          │          │
│  ┌───────▼───────┐  │
│  │ Risk Manager  │  │
│  │ Calculate     │  │
│  │ Position Size │  │
│  └───────┬───────┘  │
│          │          │
│  ┌───────▼───────┐  │
│  │ Generate      │  │
│  │ Trading Signal│  │
│  └───────┬───────┘  │
└──────────┼──────────┘
           │ publishes
           │ trading.signal
           ▼
┌─────────────────────┐
│  Event Bus          │
│  (Redis Pub/Sub)    │
└─────────────────────┘
```

## Components

### ExecutionEngine

The main orchestrator that:
1. Subscribes to `ai.high_value_signal` topic on Event Bus
2. Queries User Center API for matching EA profiles based on signal symbols
3. Calculates position sizes via Risk Manager
4. Generates trading signals with entry, stop loss, and take profit levels
5. Publishes trading signals to `trading.signal` topic

### RiskManager

Handles position sizing and risk calculations:
- Calculates position size based on risk percentage and price levels
- Enforces risk limits (max positions, total risk exposure)
- Supports multiple position sizing methods (fixed percentage, Kelly criterion, etc.)
- Implements adaptive risk scaling based on recent performance

**Note:** Current implementation is a placeholder stub. Full implementation will be completed in Task 21.

## Usage

### Basic Setup

```python
from system_core.event_bus import EventBus
from system_core.execution_engine import ExecutionEngine, RiskManager

# Initialize Event Bus
event_bus = EventBus(redis_url="redis://localhost:6379")
await event_bus.connect()

# Initialize Execution Engine
execution_engine = ExecutionEngine(
    event_bus=event_bus,
    db_session_factory=your_db_session_factory,
    risk_manager=RiskManager()
)

# Start processing signals
await execution_engine.start()
```

### Signal Flow

1. **Input**: High-value signal from AI Processing Engine
   ```python
   {
       "signal_id": "uuid",
       "source": "economic_calendar",
       "relevance_score": 85,
       "potential_impact": "high",
       "summary": "Strong NFP data...",
       "related_symbols": ["EURUSD", "GBPUSD"],
       "confidence": 0.85,
       "reasoning": "..."
   }
   ```

2. **Processing**:
   - Match EA profiles with overlapping symbols
   - Calculate position size based on risk parameters
   - Determine trading direction from signal analysis
   - Calculate entry, stop loss, and take profit levels

3. **Output**: Trading signal published to Event Bus
   ```python
   {
       "signal_id": "uuid",
       "ea_profile_id": "uuid",
       "symbol": "EURUSD",
       "direction": "long",
       "volume": 0.5,
       "entry_price": 1.0850,
       "stop_loss": 1.0740,
       "take_profit": 1.0960,
       "confidence_score": 0.85,
       "reasoning": "AI Analysis Summary: ...",
       "timestamp": "2024-01-01T12:00:00Z"
   }
   ```

## Configuration

### EA Profile Requirements

EA profiles must include:
- `symbols`: Array of trading symbols (e.g., ["EURUSD", "GBPUSD"])
- `risk_per_trade`: Risk percentage per trade (e.g., 0.02 for 2%)
- `max_positions`: Maximum concurrent positions
- `max_total_risk`: Maximum total risk exposure
- `auto_execution`: Whether to execute trades automatically

### Database Schema

The Execution Engine queries the following tables:
- `ea_profiles`: EA configurations
- `users`: User information
- `trades`: Trade execution records (for risk calculations)

## Logging

The Execution Engine provides structured logging for:
- Signal reception and processing
- EA profile matching
- Position size calculations
- Trading signal generation
- Event publishing

Example log output:
```
2024-01-01 12:00:00 - ExecutionEngine - INFO - Received high-value signal: abc-123, relevance_score=85, symbols=['EURUSD']
2024-01-01 12:00:01 - ExecutionEngine - INFO - Found 2 matching EA profile(s) for signal abc-123
2024-01-01 12:00:02 - ExecutionEngine - INFO - Generated trading signal: def-456, EA=Momentum Strategy, symbol=EURUSD, direction=long, volume=0.5
2024-01-01 12:00:03 - ExecutionEngine - INFO - Published trading signal def-456 to topic 'trading.signal'
```

## Requirements Validation

This implementation satisfies the following requirements:

### Requirement 10.1
✅ Subscribes to Event Bus topic "ai.high_value_signal" at startup

### Requirement 10.2
✅ Queries User Center API (database) for matching EA profiles based on signal symbols

### Requirement 10.3
✅ Skips processing when no matching EA profiles found and logs the reason

### Requirement 10.4
✅ Calls Risk Manager to calculate position size based on EA profile risk_per_trade

### Requirement 10.5
✅ Generates TradingSignal with all required fields: symbol, direction, volume, entry_price, stop_loss, take_profit, confidence_score, reasoning, timestamp

### Requirement 10.6
✅ Includes AI analysis summary and suggested actions in reasoning field

### Requirement 10.7
✅ Publishes generated trading signals to Event Bus topic "trading.signal"

### Requirement 10.8
✅ Logs all generated signals with EA profile, risk calculation details, and signal parameters

## Testing

Run the test suite:
```bash
pytest tests/test_execution_engine.py -v
```

Test coverage includes:
- Initialization and lifecycle (start/stop)
- High-value signal handling
- EA profile matching
- Trading signal generation
- Direction determination
- Price level calculation
- Reasoning text building
- Risk Manager position sizing

## Future Enhancements (Task 21+)

- Full Risk Manager implementation with:
  - Multiple position sizing methods
  - Risk limit enforcement
  - Adaptive risk scaling
  - Current exposure tracking
- Broker adapter integration for trade execution
- Circuit breaker implementation
- Advanced price level calculation using market data
- Support for different order types (market, limit, stop)

## Example

See `examples/execution_engine_example.py` for a complete working example.
