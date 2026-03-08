"""
Factor-Based Backtest Engine for OpenFi Lite.

This module provides factor-specific backtesting functionality, including:
- Factor signal generation
- Factor-based entry/exit logic
- Integration with factor calculation engine
- Storage of results to database
"""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID
import pandas as pd

from system_core.backtest.core import (
    BacktestCore,
    BacktestConfig,
    BacktestResult,
    TradingSignal,
    SignalType,
)
from system_core.config import get_logger
from system_core.database import get_db_client
from system_core.factor_system.models import BacktestResult as BacktestResultModel

logger = get_logger(__name__)

class FactorBacktest:
    """
    Factor-based backtest engine.
    
    This class implements backtesting for factor-based strategies:
    - Generates trading signals from factor values
    - Executes backtest using BacktestCore
    - Stores results to database
    """
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        """
        Initialize factor backtest engine.
        
        Args:
            config: Backtest configuration (uses defaults if None)
        """
        self.config = config or BacktestConfig()
        self.core = BacktestCore(self.config)
        
        logger.info("factor_backtest_initialized",
                   initial_capital=self.config.initial_capital)
    
    def run(
        self,
        strategy_name: str,
        factor_values: pd.DataFrame,
        market_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        entry_threshold: float = 0.7,
        exit_threshold: float = 0.3,
        top_n: Optional[int] = None,
        user_id: Optional[UUID] = None,
        strategy_config: Optional[dict[str, Any]] = None
    ) -> BacktestResult:
        """
        Run factor-based backtest.
        
        Args:
            strategy_name: Name of the strategy
            factor_values: DataFrame with factor values (columns: date, symbol, value)
            market_data: Historical market data (columns: date, symbol, open, high, low, close, volume)
            start_date: Backtest start date
            end_date: Backtest end date
            entry_threshold: Factor value threshold for entry (percentile or absolute)
            exit_threshold: Factor value threshold for exit
            top_n: Number of top-ranked symbols to trade (alternative to threshold)
            user_id: User ID for database storage
            strategy_config: Additional strategy configuration
            
        Returns:
            BacktestResult with complete simulation results
        """
        logger.info("factor_backtest_started",
                   strategy_name=strategy_name,
                   start_date=start_date.isoformat(),
                   end_date=end_date.isoformat(),
                   entry_threshold=entry_threshold,
                   top_n=top_n)
        
        # Detect forward-looking bias in factor data if enabled
        if self.config.enable_lookahead_detection:
            # Pre-validate factor data timestamps
            factor_values_copy = factor_values.copy()
            factor_values_copy['date'] = pd.to_datetime(factor_values_copy['date'])
            
            # Check if any factor data is from the future
            future_factors = factor_values_copy[factor_values_copy['date'] > end_date]
            if len(future_factors) > 0:
                logger.warning("future_factor_data_detected",
                             num_rows=len(future_factors),
                             end_date=end_date.isoformat())
        
        # Generate trading signals from factor values
        signals = self._generate_signals(
            factor_values=factor_values,
            market_data=market_data,
            start_date=start_date,
            end_date=end_date,
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold,
            top_n=top_n
        )
        
        logger.info("signals_generated",
                   total_signals=len(signals))
        
        # Run backtest simulation with factor data for lookahead detection
        result = self.core.simulate_trades(
            signals=signals,
            market_data=market_data,
            start_date=start_date,
            end_date=end_date,
            factor_data=factor_values
        )
        
        # Update strategy name
        result.strategy_name = strategy_name
        
        # Store result to database if user_id provided
        if user_id:
            self._store_result(result, user_id, strategy_config or {})
        
        logger.info("factor_backtest_completed",
                   strategy_name=strategy_name,
                   total_trades=result.metrics.total_trades,
                   total_return=result.metrics.total_return,
                   sharpe_ratio=result.metrics.sharpe_ratio)
        
        return result
    
    def _generate_signals(
        self,
        factor_values: pd.DataFrame,
        market_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        entry_threshold: float,
        exit_threshold: float,
        top_n: Optional[int]
    ) -> list[TradingSignal]:
        """
        Generate trading signals from factor values.
        
        Strategy logic:
        - Entry: Buy symbols with factor values above entry_threshold (or top N)
        - Exit: Sell symbols when factor values fall below exit_threshold
        - Rebalance: Check signals daily
        
        Args:
            factor_values: DataFrame with factor values
            market_data: Historical market data
            start_date: Start date
            end_date: End date
            entry_threshold: Entry threshold
            exit_threshold: Exit threshold
            top_n: Number of top symbols to trade
            
        Returns:
            List of trading signals
        """
        signals = []
        
        # Ensure date columns are datetime
        factor_values = factor_values.copy()
        factor_values['date'] = pd.to_datetime(factor_values['date'])
        
        # Get unique trading dates
        trading_dates = sorted(factor_values['date'].unique())
        trading_dates = [d for d in trading_dates if start_date <= d <= end_date]
        
        # Track current positions
        current_positions = set()
        
        for current_date in trading_dates:
            # Get factor values for current date
            date_factors = factor_values[factor_values['date'] == current_date].copy()
            
            if len(date_factors) == 0:
                continue
            
            # Rank symbols by factor value
            date_factors = date_factors.sort_values('value', ascending=False)
            
            # Determine entry candidates
            if top_n is not None:
                # Use top N ranking
                entry_candidates = set(date_factors.head(top_n)['symbol'].tolist())
            else:
                # Use threshold
                # Calculate percentile threshold
                threshold_value = date_factors['value'].quantile(entry_threshold)
                entry_candidates = set(
                    date_factors[date_factors['value'] >= threshold_value]['symbol'].tolist()
                )
            
            # Determine exit candidates (symbols below exit threshold)
            if top_n is not None:
                # Exit if not in top N anymore
                exit_candidates = current_positions - entry_candidates
            else:
                # Use exit threshold
                exit_threshold_value = date_factors['value'].quantile(exit_threshold)
                exit_symbols = set(
                    date_factors[date_factors['value'] < exit_threshold_value]['symbol'].tolist()
                )
                exit_candidates = current_positions & exit_symbols
            
            # Generate exit signals
            for symbol in exit_candidates:
                signals.append(TradingSignal(
                    date=current_date,
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    quantity=0,  # Close entire position
                    metadata={'reason': 'factor_exit', 'date': current_date.isoformat()}
                ))
                current_positions.remove(symbol)
            
            # Generate entry signals
            new_entries = entry_candidates - current_positions
            for symbol in new_entries:
                signals.append(TradingSignal(
                    date=current_date,
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    quantity=0,  # Use default position sizing
                    metadata={'reason': 'factor_entry', 'date': current_date.isoformat()}
                ))
                current_positions.add(symbol)
        
        # Close all positions at end date
        for symbol in current_positions:
            signals.append(TradingSignal(
                date=end_date,
                symbol=symbol,
                signal_type=SignalType.CLOSE,
                quantity=0,
                metadata={'reason': 'backtest_end', 'date': end_date.isoformat()}
            ))
        
        return signals
    
    def _store_result(
        self,
        result: BacktestResult,
        user_id: UUID,
        strategy_config: dict[str, Any]
    ):
        """
        Store backtest result to database.
        
        Args:
            result: Backtest result
            user_id: User ID
            strategy_config: Strategy configuration
        """
        try:
            with get_db_client() as session:
                # Convert equity curve to JSON
                equity_curve_json = result.equity_curve.to_dict(orient='records')
                
                # Convert trades to JSON
                trade_details_json = [
                    {
                        'trade_id': t.trade_id,
                        'symbol': t.symbol,
                        'entry_date': t.entry_date.isoformat(),
                        'entry_price': float(t.entry_price),
                        'quantity': float(t.quantity),
                        'exit_date': t.exit_date.isoformat() if t.exit_date else None,
                        'exit_price': float(t.exit_price) if t.exit_price else None,
                        'pnl': float(t.pnl) if t.pnl else None,
                        'commission': float(t.commission),
                        'slippage': float(t.slippage),
                        'metadata': t.metadata
                    }
                    for t in result.trades
                ]
                
                # Create database record
                db_result = BacktestResultModel(
                    user_id=user_id,
                    strategy_name=result.strategy_name,
                    strategy_config=strategy_config,
                    start_date=result.start_date.date() if isinstance(result.start_date, datetime) else result.start_date,
                    end_date=result.end_date.date() if isinstance(result.end_date, datetime) else result.end_date,
                    initial_capital=result.initial_capital,
                    final_capital=result.final_capital,
                    total_return=float(result.metrics.total_return),
                    annual_return=float(result.metrics.annual_return),
                    max_drawdown=float(result.metrics.max_drawdown),
                    sharpe_ratio=float(result.metrics.sharpe_ratio),
                    win_rate=float(result.metrics.win_rate),
                    profit_loss_ratio=float(result.metrics.profit_loss_ratio),
                    total_trades=result.metrics.total_trades,
                    equity_curve=equity_curve_json,
                    trade_details=trade_details_json
                )
                
                session.add(db_result)
                session.commit()
                
                logger.info("backtest_result_stored",
                           backtest_id=str(db_result.id),
                           strategy_name=result.strategy_name)
                
        except Exception as e:
            logger.error("failed_to_store_backtest_result",
                        error=str(e),
                        strategy_name=result.strategy_name)
            # Don't raise - backtest succeeded even if storage failed
    
    def run_multi_factor(
        self,
        strategy_name: str,
        factor_values_list: list[pd.DataFrame],
        factor_weights: list[float],
        market_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        entry_threshold: float = 0.7,
        exit_threshold: float = 0.3,
        top_n: Optional[int] = None,
        user_id: Optional[UUID] = None,
        strategy_config: Optional[dict[str, Any]] = None
    ) -> BacktestResult:
        """
        Run backtest with multiple factors combined.
        
        Args:
            strategy_name: Name of the strategy
            factor_values_list: List of DataFrames with factor values
            factor_weights: Weights for each factor (must sum to 1.0)
            market_data: Historical market data
            start_date: Backtest start date
            end_date: Backtest end date
            entry_threshold: Entry threshold for combined factor
            exit_threshold: Exit threshold for combined factor
            top_n: Number of top symbols to trade
            user_id: User ID for database storage
            strategy_config: Additional strategy configuration
            
        Returns:
            BacktestResult with complete simulation results
        """
        logger.info("multi_factor_backtest_started",
                   strategy_name=strategy_name,
                   num_factors=len(factor_values_list),
                   weights=factor_weights)
        
        # Validate weights
        if abs(sum(factor_weights) - 1.0) > 0.001:
            raise ValueError(f"Factor weights must sum to 1.0, got {sum(factor_weights)}")
        
        if len(factor_values_list) != len(factor_weights):
            raise ValueError("Number of factors must match number of weights")
        
        # Combine factors with weights
        combined_factors = None
        
        for factor_df, weight in zip(factor_values_list, factor_weights):
            factor_df = factor_df.copy()
            factor_df['weighted_value'] = factor_df['value'] * weight
            
            if combined_factors is None:
                combined_factors = factor_df[['date', 'symbol', 'weighted_value']].copy()
            else:
                combined_factors = combined_factors.merge(
                    factor_df[['date', 'symbol', 'weighted_value']],
                    on=['date', 'symbol'],
                    how='outer',
                    suffixes=('', '_new')
                )
                # Sum weighted values
                value_cols = [c for c in combined_factors.columns if 'weighted_value' in c]
                combined_factors['weighted_value'] = combined_factors[value_cols].sum(axis=1)
                # Drop extra columns
                combined_factors = combined_factors[['date', 'symbol', 'weighted_value']]
        
        # Rename to 'value' for consistency
        combined_factors = combined_factors.rename(columns={'weighted_value': 'value'})
        
        # Run backtest with combined factors
        return self.run(
            strategy_name=strategy_name,
            factor_values=combined_factors,
            market_data=market_data,
            start_date=start_date,
            end_date=end_date,
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold,
            top_n=top_n,
            user_id=user_id,
            strategy_config=strategy_config
        )
