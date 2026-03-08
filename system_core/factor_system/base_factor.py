"""
Base Factor Class

Defines the interface that all factors must implement.
Provides common functionality and validation for factor calculations.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

import pandas as pd

class BaseFactor(ABC):
    """
    Abstract base class for all factors.
    
    All user-defined factors must inherit from this class and implement
    the calculate() method. This ensures a consistent interface across
    all factors in the system.
    
    Attributes:
        name: Factor name (unique identifier)
        description: Human-readable description of the factor
        category: Factor category ('technical', 'fundamental', 'sentiment', 'alternative')
        version: Factor version string
        required_data: List of required data sources
        parameters: Dictionary of factor parameters with metadata
    """
    
    # Factor metadata (must be defined by subclasses)
    name: str = ""
    description: str = ""
    category: str = ""  # 'technical', 'fundamental', 'sentiment', 'alternative'
    version: str = "1.0.0"
    
    # Data dependencies
    required_data: list[str] = []  # e.g., ['market_data', 'news_data', 'fundamental_data']
    
    # Parameter definitions
    # Example: {
    #     'lookback_period': {
    #         'type': 'int',
    #         'default': 20,
    #         'min': 1,
    #         'max': 252,
    #         'description': 'Lookback period in days'
    #     }
    # }
    parameters: dict[str, dict[str, Any]] = {}
    
    def __init__(self):
        """Initialize factor."""
        self._validate_metadata()
    
    def _validate_metadata(self) -> None:
        """
        Validate factor metadata.
        
        Raises:
            ValueError: If metadata is invalid
        """
        if not self.name:
            raise ValueError("Factor name must be defined")
        
        if not self.description:
            raise ValueError("Factor description must be defined")
        
        if self.category not in ['technical', 'fundamental', 'sentiment', 'alternative', '']:
            raise ValueError(f"Invalid category: {self.category}")
        
        if not self.required_data:
            raise ValueError("Factor must specify required data sources")
    
    @abstractmethod
    def calculate(
        self,
        data: dict[str, pd.DataFrame],
        params: Optional[dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Calculate factor values.
        
        This is the main method that must be implemented by all factors.
        It receives input data and parameters, and returns calculated factor values.
        
        Args:
            data: Dictionary of input data
                  Keys are data source names (e.g., 'market_data', 'news_data')
                  Values are pandas DataFrames with the data
            params: Optional dictionary of factor parameters
                    If not provided, default parameters will be used
        
        Returns:
            DataFrame with columns: ['symbol', 'date', 'value']
            - symbol: Asset symbol (e.g., 'AAPL', 'GOOGL')
            - date: Date of the factor value
            - value: Calculated factor value (float)
        
        Raises:
            ValueError: If input data is invalid
            RuntimeError: If calculation fails
        
        Example:
            >>> data = {
            ...     'market_data': pd.DataFrame({
            ...         'symbol': ['AAPL', 'AAPL'],
            ...         'date': ['2023-01-01', '2023-01-02'],
            ...         'close': [150.0, 152.0]
            ...     })
            ... }
            >>> params = {'lookback_period': 20}
            >>> result = factor.calculate(data, params)
            >>> print(result)
               symbol        date     value
            0    AAPL  2023-01-01  0.013333
            1    AAPL  2023-01-02  0.013333
        """
        pass
    
    def validate_data(self, data: dict[str, pd.DataFrame]) -> bool:
        """
        Validate input data completeness.
        
        Checks if all required data sources are present and not empty.
        
        Args:
            data: Dictionary of input data
        
        Returns:
            True if data is valid, False otherwise
        """
        for required in self.required_data:
            if required not in data:
                return False
            if data[required].empty:
                return False
        return True
    
    def get_parameter_value(
        self,
        params: Optional[dict[str, Any]],
        param_name: str
    ) -> Any:
        """
        Get parameter value with fallback to default.
        
        Args:
            params: User-provided parameters
            param_name: Parameter name
        
        Returns:
            Parameter value (user-provided or default)
        
        Raises:
            ValueError: If parameter not defined and no default available
        """
        if param_name not in self.parameters:
            raise ValueError(f"Unknown parameter: {param_name}")
        
        param_def = self.parameters[param_name]
        
        # Use user-provided value if available
        if params and param_name in params:
            value = params[param_name]
            # Validate type
            expected_type = param_def.get('type', 'any')
            if expected_type != 'any':
                if expected_type == 'int' and not isinstance(value, int):
                    raise ValueError(f"Parameter {param_name} must be int, got {type(value)}")
                elif expected_type == 'float' and not isinstance(value, (int, float)):
                    raise ValueError(f"Parameter {param_name} must be float, got {type(value)}")
                elif expected_type == 'str' and not isinstance(value, str):
                    raise ValueError(f"Parameter {param_name} must be str, got {type(value)}")
            
            # Validate range
            if 'min' in param_def and value < param_def['min']:
                raise ValueError(f"Parameter {param_name} must be >= {param_def['min']}")
            if 'max' in param_def and value > param_def['max']:
                raise ValueError(f"Parameter {param_name} must be <= {param_def['max']}")
            
            return value
        
        # Use default value
        if 'default' not in param_def:
            raise ValueError(f"Parameter {param_name} has no default value")
        
        return param_def['default']
    
    def get_metadata(self) -> dict[str, Any]:
        """
        Get factor metadata.
        
        Returns:
            Dictionary containing factor metadata
        """
        return {
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'version': self.version,
            'required_data': self.required_data,
            'parameters': self.parameters
        }
    
    def __repr__(self) -> str:
        """String representation of factor."""
        return f"<{self.__class__.__name__}(name={self.name}, category={self.category})>"
