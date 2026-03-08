# Unified Backtest Engine

## Overview

The unified backtest engine provides a shared backtesting infrastructure for both EA (Expert Advisor) and factor-based strategies. It implements an event-driven simulation architecture with position management and comprehensive performance metrics calculation.

## Architecture

### Core Components

1. **BacktestCore** (`core.py`)
   - Event-driven trade simulation
   - Position and portfolio management
   - Performance metrics calculation
   - Equity curve generation

2. **FactorBacktest** (`factor_backtest.py`)
   - Factor signal generation
   - Single and multi-factor strategies
   - Database integration
   - Factor-specific entry/exit logic

### Design Principles

- **Unified Infrastructure**: Both EA and factor strategies use the same core simulation engine
- **Event-Driven**: Processes market data chronologically to avoid look-ahead bias
- **Modular**: Easy to extend with new strategy types
- **Database Integration**: Stores results with unified schema supporting multiple strategy types

## Usage

### Basic Factor Backtest

```python
from datetime import datetime
from system_core.backtest import FactorBacktest, BacktestConfig
import pandas as pd

# Configure backtest
config = BacktestConfig(
    initial_capital=100000.0,
    commission_rate=0.001,
    slippage_rate=0.0005,
    position_size_pct=0.1
)

# Initialize backtest engine
backtest = FactorBacktest(config)

# Prepare factor values (DataFrame with columns: date, symbol, value)
factor_values = pd.DataFrame([
    {'date': datetime(2023, 1, 1), 'symbol': 'AAPL', 'value': 0.85},
    {'date': datetime(2023, 1, 1), 'symbol': 'GOOGL', 'value': 0.65},
    # ... more data
])

# Prepare market data (DataFrame with columns: date, symbol, open, high, low, close, volume)
market_data = pd.DataFrame([
    {'date': datetime(2023, 1, 1), 'symbol': 'AAPL', 'close': 150.0, 'volume': 1000000},
    # ... more data
])

# Run backtest
result = backtest.run(
    strategy_name="Momentum Strategy",
    factor_values=factor_values,
    market_data=market_data,
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31),
    entry_threshold=0.7,  # Enter top 30% by factor value
    exit_threshold=0.3,   # Exit when below 70th percentile
    user_id=user_id  # Optional: store to database
)

# Access results
print(f"Total Return: {result.metrics.total_return:.2%}")
print(f"Sharpe Ratio: {result.metrics.sharpe_ratio:.2f}")
print(f"Max Drawdown: {result.metrics.max_drawdown:.2%}")
print(f"Win Rate: {result.metrics.win_rate:.2%}")
print(f"Total Trades: {result.metrics.total_trades}")
```

### Multi-Factor Backtest

```python
# Combine multiple factors with weights
result = backtest.run_multi_factor(
    strategy_name="Multi-Factor Strategy",
    factor_values_list=[momentum_factors, value_factors, sentiment_factors],
    factor_weights=[0.5, 0.3, 0.2],  # Must sum to 1.0
    market_data=market_data,
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31),
    top_n=10,  # Trade top 10 symbols
    user_id=user_id
)
```

### Top-N Ranking Strategy

```python
# Instead of threshold, use top N ranking
result = backtest.run(
    strategy_name="Top 5 Strategy",
    factor_values=factor_values,
    market_data=market_data,
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31),
    top_n=5,  # Always hold top 5 symbols
    user_id=user_id
)
```

## Configuration Options

### BacktestConfig

```python
@dataclass
class BacktestConfig:
    initial_capital: float = 100000.0      # Starting capital
    commission_rate: float = 0.001         # 0.1% commission
    slippage_rate: float = 0.0005          # 0.05% slippage
    leverage: float = 1.0                  # Maximum leverage
    position_size_pct: float = 0.1         # 10% per position
    max_position_size: float = 0.2         # 20% max per position
    risk_free_rate: float = 0.02           # 2% risk-free rate for Sharpe
    enable_lookahead_detection: bool = True  # Enable forward-looking bias detection
    strict_lookahead_check: bool = False   # Raise error vs warning on bias
```

## Forward-Looking Bias Detection

The backtest engine includes comprehensive forward-looking bias detection to ensure strategies don't inadvertently use future data. This feature validates:

- Signal timestamps against available market data
- Factor data timestamps against signal dates
- Data timestamps during simulation

### Basic Usage

```python
# Enable lookahead detection (default)
config = BacktestConfig(
    initial_capital=100000.0,
    enable_lookahead_detection=True,
    strict_lookahead_check=False  # Log warnings, don't fail
)

result = backtest.run(...)

# Check for violations
if result.lookahead_violations:
    print(f"Found {len(result.lookahead_violations)} lookahead violations")
    for violation in result.lookahead_violations:
        print(f"  {violation['type']}: {violation['message']}")
```

### Strict Mode

```python
# Fail immediately on lookahead bias
config = BacktestConfig(
    enable_lookahead_detection=True,
    strict_lookahead_check=True  # Raise error on violation
)

try:
    result = backtest.run(...)
except LookaheadBiasError as e:
    print(f"Lookahead bias detected: {e}")
```

For detailed documentation on forward-looking bias detection, see [LOOKAHEAD_DETECTION.md](./LOOKAHEAD_DETECTION.md).

## Performance Metrics

The backtest engine calculates comprehensive performance metrics:

- **Total Return**: Overall return percentage
- **Annual Return**: Annualized return
- **Max Drawdown**: Maximum peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return (annualized)
- **Win Rate**: Percentage of profitable trades
- **Profit/Loss Ratio**: Average win / average loss
- **Total Trades**: Number of completed trades
- **Winning/Losing Trades**: Count of profitable/unprofitable trades
- **Average Win/Loss**: Average P&L per winning/losing trade
- **Max Consecutive Wins/Losses**: Longest winning/losing streak

## Database Schema

Results are stored in the `backtest_results` table with unified schema:

```sql
CREATE TABLE backtest_results (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    strategy_type VARCHAR(20) NOT NULL,  -- 'ea', 'factor', 'combined'
    strategy_name VARCHAR(100) NOT NULL,
    ea_id VARCHAR(100),                  -- For EA strategies
    factor_ids JSONB,                    -- For factor strategies
    strategy_config JSONB NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital NUMERIC(20, 2) NOT NULL,
    final_capital NUMERIC(20, 2),
    total_return NUMERIC(10, 4),
    annual_return NUMERIC(10, 4),
    max_drawdown NUMERIC(10, 4),
    sharpe_ratio NUMERIC(10, 4),
    win_rate NUMERIC(5, 4),
    profit_loss_ratio NUMERIC(10, 4),
    total_trades INTEGER,
    equity_curve JSONB,
    trade_details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Integration with Factor System

The backtest engine integrates seamlessly with the factor calculation engine:

```python
from system_core.factor_system.engine import FactorEngine
from system_core.backtest import FactorBacktest

# Calculate factor values
factor_engine = FactorEngine()
factor_values = factor_engine.calculate_factor(
    factor_id="momentum_20d",
    symbols=["AAPL", "GOOGL", "MSFT"],
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31)
)

# Run backtest with calculated factors
backtest = FactorBacktest()
result = backtest.run(
    strategy_name="Momentum Strategy",
    factor_values=factor_values,
    market_data=market_data,
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31),
    user_id=user_id
)
```

## Future Extensions

### EA Backtest (Planned)

```python
from system_core.backtest import EABacktest

# EA-specific backtest implementation
ea_backtest = EABacktest(config)
result = ea_backtest.run(
    ea_id="my_ea",
    market_data=market_data,
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31)
)
```

### Combined EA + Factor Strategy (Planned)

```python
from system_core.backtest import CombinedBacktest

# Combine EA signals with factor filtering
combined = CombinedBacktest(config)
result = combined.run(
    ea_id="my_ea",
    factor_ids=["momentum_20d", "value_score"],
    factor_weights=[0.6, 0.4],
    market_data=market_data,
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31)
)
```

## Testing

Unit tests are provided in `tests/`:

- `test_backtest_core.py`: Core engine functionality
- `test_factor_backtest.py`: Factor-specific features

Run tests with:
```bash
pytest tests/test_backtest_core.py -v
pytest tests/test_factor_backtest.py -v
```

## Implementation Notes

### Event-Driven Architecture

The backtest engine processes market data chronologically:

1. **Market Event**: New market data arrives
2. **Signal Generation**: Strategy generates trading signals
3. **Order Execution**: Signals are converted to orders
4. **Position Update**: Portfolio positions are updated
5. **Equity Recording**: Portfolio value is recorded

This ensures no look-ahead bias and realistic simulation.

### Position Sizing

Default position sizing uses a percentage of portfolio value:

```python
position_value = portfolio_value * position_size_pct
quantity = position_value / current_price
```

Custom position sizing can be implemented by providing explicit quantities in signals.

### Commission and Slippage

Both commission and slippage are applied to each trade:

- **Commission**: Percentage of trade value (applied to both entry and exit)
- **Slippage**: Simulates market impact (buy at higher price, sell at lower price)

### Performance Calculation

Performance metrics are calculated from:

1. **Trade Records**: Individual trade P&L, win/loss statistics
2. **Equity Curve**: Time series of portfolio value for drawdown and Sharpe ratio

## Requirements

- Python 3.8+
- pandas >= 2.0.0
- numpy >= 1.20.0
- SQLAlchemy >= 2.0.0
- PostgreSQL (for database storage)

## License

Part of OpenFi Lite quantitative trading platform.
