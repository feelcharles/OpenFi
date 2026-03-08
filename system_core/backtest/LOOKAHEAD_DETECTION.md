# Forward-Looking Bias Detection

## Overview

Forward-looking bias (前视偏差) is a critical issue in backtesting where a strategy inadvertently uses information that would not have been available at the time of the trading decision. This can lead to unrealistic performance results and false confidence in a strategy.

The OpenFi Lite backtest engine includes comprehensive forward-looking bias detection to help identify and prevent this issue.

## Features

### 1. Signal Timestamp Validation

The system validates that all trading signals have corresponding market data available at the signal date. If a signal is generated before market data is available, it indicates potential lookahead bias.

**Example violation:**
- Signal date: 2023-01-15
- Market data available from: 2023-01-20
- **Issue:** Signal appears to use future market data

### 2. Factor Data Timestamp Validation

When using factor-based strategies, the system checks that factor values used for signal generation have timestamps that are on or before the signal date.

**Example violation:**
- Signal date: 2023-01-15
- Factor data date: 2023-01-16
- **Issue:** Signal may be using future factor values

### 3. Data Timestamp Validation During Simulation

During the backtest simulation, the system continuously validates that all data used at each time step has timestamps less than or equal to the current simulation date.

**Example violation:**
- Current simulation date: 2023-06-15
- Data row timestamp: 2023-06-20
- **Issue:** Using future data during simulation

## Configuration

Forward-looking bias detection is configured through the `BacktestConfig` class:

```python
from system_core.backtest.core import BacktestConfig

config = BacktestConfig(
    initial_capital=100000.0,
    enable_lookahead_detection=True,    # Enable detection (default: True)
    strict_lookahead_check=False        # Raise error vs warning (default: False)
)
```

### Configuration Options

- **`enable_lookahead_detection`** (bool, default: True)
  - When `True`, the system performs all lookahead bias checks
  - When `False`, all checks are disabled (not recommended for production)

- **`strict_lookahead_check`** (bool, default: False)
  - When `True`, raises `LookaheadBiasError` immediately upon detecting any violation
  - When `False`, logs warnings and continues execution, collecting all violations

## Usage

### Basic Usage

```python
from system_core.backtest.core import BacktestCore, BacktestConfig
from system_core.backtest.factor_backtest import FactorBacktest

# Create config with lookahead detection
config = BacktestConfig(
    initial_capital=100000.0,
    enable_lookahead_detection=True,
    strict_lookahead_check=False
)

# Run backtest
backtest = FactorBacktest(config)
result = backtest.run(
    strategy_name="My Strategy",
    factor_values=factor_df,
    market_data=market_df,
    start_date=start_date,
    end_date=end_date
)

# Check for violations
if result.lookahead_violations:
    print(f"Found {len(result.lookahead_violations)} lookahead violations:")
    for violation in result.lookahead_violations:
        print(f"  - {violation['type']}: {violation['message']}")
```

### Strict Mode (Fail Fast)

```python
# Use strict mode to fail immediately on violations
config = BacktestConfig(
    initial_capital=100000.0,
    enable_lookahead_detection=True,
    strict_lookahead_check=True  # Raise error on violation
)

try:
    result = backtest.run(...)
except LookaheadBiasError as e:
    print(f"Lookahead bias detected: {e}")
    # Handle error appropriately
```

### Manual Detection

You can also manually check for lookahead bias before running a backtest:

```python
from system_core.backtest.core import BacktestCore

core = BacktestCore(config)

# Detect lookahead bias in signals
violations = core.detect_lookahead_bias(
    signals=trading_signals,
    market_data=market_df,
    factor_data=factor_df  # Optional
)

if violations:
    print(f"Found {len(violations)} violations")
    for v in violations:
        print(f"  {v['type']}: {v['message']}")
```

## Violation Types

### 1. `signal_future_data`

A trading signal is generated at a date where market data is not yet available, but future market data exists.

**Violation structure:**
```python
{
    'type': 'signal_future_data',
    'signal_index': 0,
    'signal_date': '2023-01-15',
    'symbol': 'AAPL',
    'message': 'Signal at 2023-01-15 for AAPL but market data not available until later dates',
    'earliest_future_date': '2023-01-20'
}
```

### 2. `factor_future_data`

A trading signal may be using factor data from the future.

**Violation structure:**
```python
{
    'type': 'factor_future_data',
    'signal_index': 0,
    'signal_date': '2023-01-15',
    'symbol': 'AAPL',
    'message': 'Signal at 2023-01-15 for AAPL may be using future factor data from 2023-01-16',
    'future_factor_date': '2023-01-16'
}
```

### 3. `data_timestamp_violation`

Data with timestamps after the current simulation date was detected during backtest execution.

**Violation structure:**
```python
{
    'type': 'data_timestamp_violation',
    'current_date': '2023-06-15',
    'data_type': 'market_data',
    'num_future_rows': 5,
    'future_dates': ['2023-06-16', '2023-06-17', ...],
    'message': 'Found 5 rows of market_data with timestamps after current date 2023-06-15'
}
```

## Best Practices

### 1. Always Enable Detection in Development

Keep `enable_lookahead_detection=True` during strategy development to catch issues early.

```python
# Development config
dev_config = BacktestConfig(
    enable_lookahead_detection=True,
    strict_lookahead_check=True  # Fail fast during development
)
```

### 2. Review Violations Before Production

Before deploying a strategy, review all lookahead violations:

```python
result = backtest.run(...)

if result.lookahead_violations:
    # Log violations for review
    for v in result.lookahead_violations:
        logger.warning(f"Lookahead violation: {v}")
    
    # Decide whether to proceed
    if len(result.lookahead_violations) > threshold:
        raise ValueError("Too many lookahead violations")
```

### 3. Ensure Proper Data Alignment

Make sure your data is properly aligned:

- **Market data**: Should have timestamps at market close or end of trading day
- **Factor data**: Should be calculated using only data available up to that timestamp
- **Signals**: Should be generated using only data with timestamps <= signal date

### 4. Use Point-in-Time Data

When possible, use point-in-time data that reflects what was actually known at each historical date:

```python
# Good: Point-in-time factor calculation
def calculate_factor(data, current_date):
    # Only use data up to current_date
    historical_data = data[data['date'] <= current_date]
    return compute_factor_value(historical_data)

# Bad: Using all data including future
def calculate_factor_bad(data, current_date):
    # This uses all data, including future!
    return compute_factor_value(data)
```

## Limitations

### 1. Cannot Detect All Lookahead Bias

The detection system can only identify timestamp-based violations. It cannot detect:

- Lookahead bias in factor calculation logic
- Use of revised/restated data that wasn't available historically
- Survivorship bias
- Data snooping bias

### 2. False Positives

In some cases, the system may flag false positives:

- Data gaps (e.g., holidays, halted trading)
- Different data frequencies (daily signals with intraday data)
- Time zone differences

Review violations carefully to distinguish real issues from false positives.

## Testing

The forward-looking bias detection includes comprehensive tests:

```bash
# Run lookahead detection tests
pytest tests/test_lookahead_detection.py -v

# Run all backtest tests
pytest tests/test_backtest_core.py tests/test_factor_backtest.py tests/test_lookahead_detection.py -v
```

## Implementation Details

### Detection Algorithm

1. **Pre-simulation validation:**
   - Check all signals against available market data dates
   - Check all signals against factor data dates (if provided)
   - Identify signals that may use future data

2. **During simulation:**
   - At each time step, validate that all data has timestamps <= current date
   - Log violations but continue execution (unless strict mode)

3. **Post-simulation:**
   - Collect all violations in the result object
   - Log summary of violations

### Performance Impact

The lookahead detection adds minimal overhead:

- Pre-simulation checks: O(n) where n = number of signals
- During simulation: O(1) per time step (only validates current data)
- Memory: Stores violation records (typically small)

For most backtests, the performance impact is negligible (<1% overhead).

## Related Requirements

This implementation satisfies requirement **5.11** from the factor analysis system specification:

> **5.11**: THE Backtest_Engine SHALL support forward-looking bias detection (avoid using future data)

## See Also

- [Backtest Core Documentation](./README.md)
- [Factor Backtest Documentation](./factor_backtest.py)
- [Testing Guide](../../tests/README.md)
