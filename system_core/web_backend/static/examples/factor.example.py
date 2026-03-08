"""
Example Factor - Momentum Factor
示例因子 - 动量因子

This is an example factor that calculates momentum based on price changes.
这是一个基于价格变化计算动量的示例因子。
"""

import pandas as pd
import numpy as np
from typing import Optional

class MomentumFactor:
    """
    Momentum Factor
    
    Calculates momentum score based on historical price performance.
    """
    
    def __init__(self, lookback_period: int = 20, min_periods: int = 10):
        """
        Initialize momentum factor.
        
        Args:
            lookback_period: Number of periods to look back
            min_periods: Minimum number of periods required
        """
        self.lookback_period = lookback_period
        self.min_periods = min_periods
        self.name = "momentum"
        self.version = "1.0.0"
    
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate momentum factor.
        
        Args:
            data: DataFrame with 'close' column
            
        Returns:
            Series with momentum scores
        """
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")
        
        # Calculate returns
        returns = data['close'].pct_change(self.lookback_period)
        
        # Calculate momentum score (standardized returns)
        momentum = (returns - returns.mean()) / returns.std()
        
        return momentum
    
    def rank(self, scores: pd.Series, ascending: bool = False) -> pd.Series:
        """
        Rank stocks by momentum score.
        
        Args:
            scores: Momentum scores
            ascending: Rank in ascending order
            
        Returns:
            Ranked scores
        """
        return scores.rank(ascending=ascending, pct=True)
    
    def filter(self, scores: pd.Series, threshold: float = 0.7) -> list[str]:
        """
        Filter stocks by momentum threshold.
        
        Args:
            scores: Momentum scores
            threshold: Minimum percentile threshold
            
        Returns:
            List of stock symbols that pass the filter
        """
        ranked = self.rank(scores)
        return ranked[ranked >= threshold].index.tolist()
    
    def backtest(self, 
                 data: dict[str, pd.DataFrame], 
                 rebalance_freq: str = 'M',
                 top_n: int = 10) -> pd.DataFrame:
        """
        Backtest momentum strategy.
        
        Args:
            data: Dictionary of DataFrames (symbol -> price data)
            rebalance_freq: Rebalancing frequency ('D', 'W', 'M')
            top_n: Number of top stocks to hold
            
        Returns:
            DataFrame with backtest results
        """
        results = []
        
        for symbol, df in data.items():
            momentum = self.calculate(df)
            
            # Simple backtest: buy when momentum > 0, sell when < 0
            signals = np.where(momentum > 0, 1, -1)
            returns = df['close'].pct_change()
            strategy_returns = signals[:-1] * returns[1:]
            
            results.append({
                'symbol': symbol,
                'total_return': strategy_returns.sum(),
                'sharpe_ratio': strategy_returns.mean() / strategy_returns.std() * np.sqrt(252),
                'max_drawdown': (strategy_returns.cumsum() - strategy_returns.cumsum().cummax()).min()
            })
        
        return pd.DataFrame(results)
    
    def get_config(self) -> Dict:
        """
        Get factor configuration.
        
        Returns:
            Configuration dictionary
        """
        return {
            'name': self.name,
            'version': self.version,
            'lookback_period': self.lookback_period,
            'min_periods': self.min_periods,
            'description': 'Momentum factor based on historical price performance'
        }

# Example usage
if __name__ == "__main__":
    # Create sample data
    dates = pd.date_range('2023-01-01', periods=100)
    data = pd.DataFrame({
        'close': np.random.randn(100).cumsum() + 100
    }, index=dates)
    
    # Initialize factor
    factor = MomentumFactor(lookback_period=20)
    
    # Calculate momentum
    momentum = factor.calculate(data)
    print("Momentum scores:")
    print(momentum.tail())
    
    # Get configuration
    config = factor.get_config()
    print("\nFactor configuration:")
    print(config)
