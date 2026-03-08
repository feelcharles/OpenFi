"""
Factor Template

Use this template to create new factors.
Copy this file and implement the calculate() method.
"""

from typing import Any, Optional

import pandas as pd
import numpy as np

from system_core.factor_system.base_factor import BaseFactor

class TemplateFactor(BaseFactor):
    """
    Template factor - replace with your factor name.
    
    Describe what this factor measures and how it works.
    """
    
    # Factor metadata
    name = "template_factor"
    description = "Template factor for demonstration"
    category = "technical"  # or 'fundamental', 'sentiment', 'alternative'
    version = "1.0.0"
    
    # Data dependencies
    required_data = ['market_data']  # List required data sources
    
    # Parameter definitions
    parameters = {
        'lookback_period': {
            'type': 'int',
            'default': 20,
            'min': 1,
            'max': 252,
            'description': 'Lookback period in days'
        },
        'threshold': {
            'type': 'float',
            'default': 0.0,
            'min': -1.0,
            'max': 1.0,
            'description': 'Threshold value'
        }
    }
    
    def calculate(
        self,
        data: dict[str, pd.DataFrame],
        params: Optional[dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Calculate factor values.
        
        Args:
            data: Dictionary of input data
                  'market_data' should contain: symbol, date, open, high, low, close, volume
            params: Optional parameters
        
        Returns:
            DataFrame with columns: ['symbol', 'date', 'value']
        """
        # Validate input data
        if not self.validate_data(data):
            raise ValueError("Invalid input data")
        
        # Get parameters
        lookback_period = self.get_parameter_value(params, 'lookback_period')
        threshold = self.get_parameter_value(params, 'threshold')
        
        # Get market data
        market_data = data['market_data'].copy()
        
        # Ensure required columns exist
        required_columns = ['symbol', 'date', 'close']
        for col in required_columns:
            if col not in market_data.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Calculate factor values
        results = []
        
        for symbol in market_data['symbol'].unique():
            # Filter data for this symbol
            symbol_data = market_data[market_data['symbol'] == symbol].sort_values('date')
            
            # Skip if insufficient data
            if len(symbol_data) < lookback_period:
                continue
            
            # Example calculation: simple momentum
            # Replace this with your actual factor logic
            symbol_data['factor_value'] = symbol_data['close'].pct_change(lookback_period)
            
            # Apply threshold if needed
            # symbol_data['factor_value'] = symbol_data['factor_value'].apply(
            #     lambda x: x if abs(x) > threshold else 0
            # )
            
            # Collect results
            for _, row in symbol_data.iterrows():
                if pd.notna(row['factor_value']):
                    results.append({
                        'symbol': symbol,
                        'date': row['date'],
                        'value': float(row['factor_value'])
                    })
        
        # Return as DataFrame
        return pd.DataFrame(results)

# Example usage (for testing)
if __name__ == "__main__":
    # Create sample data
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    sample_data = {
        'market_data': pd.DataFrame({
            'symbol': ['AAPL'] * 100,
            'date': dates,
            'open': np.random.randn(100).cumsum() + 100,
            'high': np.random.randn(100).cumsum() + 102,
            'low': np.random.randn(100).cumsum() + 98,
            'close': np.random.randn(100).cumsum() + 100,
            'volume': np.random.randint(1000000, 10000000, 100)
        })
    }
    
    # Create factor instance
    factor = TemplateFactor()
    
    # Calculate factor values
    result = factor.calculate(sample_data, {'lookback_period': 20})
    
    print("Factor calculation result:")
    print(result.head(10))
    print(f"\nTotal values calculated: {len(result)}")
