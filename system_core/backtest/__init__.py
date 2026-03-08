"""
Unified Backtest Engine for OpenFi Lite.

This module provides a unified backtesting infrastructure that supports:
- EA (Expert Advisor) strategies
- Factor-based strategies
- Combined EA + Factor strategies

The backtest engine uses an event-driven architecture to simulate historical trading
and calculate performance metrics.
"""

from system_core.backtest.core import BacktestCore, BacktestConfig, BacktestResult
from system_core.backtest.factor_backtest import FactorBacktest

__all__ = [
    "BacktestCore",
    "BacktestConfig",
    "BacktestResult",
    "FactorBacktest",
]
