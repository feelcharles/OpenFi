"""
Factor Combination Optimizer

Provides functionality for:
- Equal weighting - simple average of factor values
- IC weighting - weight by information coefficient (correlation with returns)
- Sharpe ratio maximization - optimize weights to maximize risk-adjusted returns
- Factor correlation analysis - identify redundant factors
- Dynamic weight adjustment - adapt weights based on recent performance
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
import warnings

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.factor_system.models import FactorCombination
from system_core.database import get_db_client

logger = logging.getLogger(__name__)

# Suppress scipy optimization warnings
warnings.filterwarnings('ignore', category=RuntimeWarning)

class OptimizationMethod(str, Enum):
    """Factor weight optimization methods"""
    EQUAL_WEIGHT = "equal_weight"
    IC_WEIGHTED = "ic_weighted"
    MAX_SHARPE = "max_sharpe"

class OptimizerError(Exception):
    """Raised when optimization fails"""
    pass

class FactorOptimizer:
    """
    Factor Combination Optimizer
    
    Optimizes factor weights using various methods:
    - Equal weighting: Simple average
    - IC weighting: Weight by information coefficient
    - Sharpe ratio maximization: Optimize for risk-adjusted returns
    
    Also provides:
    - Factor correlation analysis
    - Dynamic weight adjustment
    """
    
    def __init__(
        self,
        lookback_period: int = 252,
        rebalance_frequency: int = 20,
        timeout: int = 30,
        min_weight: float = 0.0,
        max_weight: float = 0.5,
        max_correlation: float = 0.8
    ):
        """
        Initialize Factor Optimizer.
        
        Args:
            lookback_period: Historical period for optimization (trading days)
            rebalance_frequency: Rebalance frequency (trading days)
            timeout: Optimization timeout in seconds
            min_weight: Minimum weight per factor
            max_weight: Maximum weight per factor
            max_correlation: Maximum allowed correlation between factors
        """
        self.lookback_period = lookback_period
        self.rebalance_frequency = rebalance_frequency
        self.timeout = timeout
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.max_correlation = max_correlation
    
    def optimize_weights(
        self,
        factor_returns: pd.DataFrame,
        method: OptimizationMethod = OptimizationMethod.MAX_SHARPE,
        constraints: Optional[Dict] = None
    ) -> dict[str, float]:
        """
        Optimize factor weights.
        
        Args:
            factor_returns: DataFrame with factor returns (columns: factor names, index: dates)
            method: Optimization method
            constraints: Optional custom constraints
        
        Returns:
            Dictionary mapping factor name to weight
        
        Raises:
            OptimizerError: If optimization fails
        """
        if factor_returns.empty:
            raise OptimizerError("Factor returns DataFrame is empty")
        
        if len(factor_returns.columns) == 0:
            raise OptimizerError("No factors provided")
        
        logger.info(
            f"Optimizing weights for {len(factor_returns.columns)} factors "
            f"using {method.value} method"
        )
        
        try:
            if method == OptimizationMethod.EQUAL_WEIGHT:
                weights = self._equal_weight(factor_returns)
            elif method == OptimizationMethod.IC_WEIGHTED:
                weights = self._ic_weighted(factor_returns)
            elif method == OptimizationMethod.MAX_SHARPE:
                weights = self._max_sharpe(factor_returns, constraints)
            else:
                raise OptimizerError(f"Unknown optimization method: {method}")
            
            # Validate weights
            self._validate_weights(weights)
            
            logger.info(
                f"Optimization completed: {method.value}",
                extra={'weights': weights}
            )
            
            return weights
            
        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            raise OptimizerError(f"Optimization failed: {e}")
    
    def _equal_weight(self, factor_returns: pd.DataFrame) -> dict[str, float]:
        """
        Equal weighting: assign equal weight to all factors.
        
        Args:
            factor_returns: Factor returns DataFrame
        
        Returns:
            Dictionary of equal weights
        """
        n_factors = len(factor_returns.columns)
        weight = 1.0 / n_factors
        
        weights = {factor: weight for factor in factor_returns.columns}
        
        logger.info(f"Equal weights assigned: {weight:.4f} per factor")
        return weights
    
    def _ic_weighted(self, factor_returns: pd.DataFrame) -> dict[str, float]:
        """
        IC weighting: weight factors by their information coefficient.
        
        Information Coefficient (IC) measures the correlation between
        factor values and subsequent returns. Higher IC = higher weight.
        
        Args:
            factor_returns: Factor returns DataFrame
        
        Returns:
            Dictionary of IC-weighted weights
        """
        # Calculate IC for each factor (correlation with mean return)
        # In practice, IC would be calculated against actual forward returns
        # Here we use the factor's own return as a proxy
        
        ics = {}
        for factor in factor_returns.columns:
            # Calculate rolling IC (correlation with next period return)
            factor_series = factor_returns[factor]
            
            # Simple IC: correlation of factor with its own next-period return
            # In real implementation, this would be correlation with asset returns
            ic = factor_series.autocorr(lag=1)
            
            # Handle NaN (no correlation)
            if pd.isna(ic):
                ic = 0.0
            
            # Use absolute IC (we care about predictive power, not direction)
            ics[factor] = abs(ic)
        
        # Normalize ICs to sum to 1.0
        total_ic = sum(ics.values())
        
        if total_ic == 0:
            # Fallback to equal weights if no IC signal
            logger.warning("All ICs are zero, falling back to equal weights")
            return self._equal_weight(factor_returns)
        
        weights = {factor: ic / total_ic for factor, ic in ics.items()}
        
        logger.info(f"IC-weighted optimization completed", extra={'ics': ics})
        return weights
    
    def _max_sharpe(
        self,
        factor_returns: pd.DataFrame,
        constraints: Optional[Dict] = None
    ) -> dict[str, float]:
        """
        Maximize Sharpe ratio: optimize weights to maximize risk-adjusted returns.
        
        Uses scipy.optimize to find weights that maximize:
        Sharpe Ratio = (Portfolio Return - Risk-Free Rate) / Portfolio Volatility
        
        Args:
            factor_returns: Factor returns DataFrame
            constraints: Optional custom constraints
        
        Returns:
            Dictionary of optimized weights
        """
        n_factors = len(factor_returns.columns)
        factor_names = list(factor_returns.columns)
        
        # Calculate mean returns and covariance matrix
        mean_returns = factor_returns.mean()
        cov_matrix = factor_returns.cov()
        
        # Handle singular covariance matrix
        if np.linalg.det(cov_matrix) == 0:
            logger.warning("Singular covariance matrix, adding regularization")
            cov_matrix = cov_matrix + np.eye(n_factors) * 1e-6
        
        # Objective function: minimize negative Sharpe ratio
        def objective(weights):
            portfolio_return = np.dot(mean_returns, weights)
            portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            # Avoid division by zero
            if portfolio_std == 0:
                return 1e10
            
            sharpe = portfolio_return / portfolio_std
            return -sharpe  # Minimize negative = maximize positive
        
        # Constraints
        constraints_list = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}  # Weights sum to 1
        ]
        
        # Apply custom constraints or defaults
        min_w = constraints.get('min_weight', self.min_weight) if constraints else self.min_weight
        max_w = constraints.get('max_weight', self.max_weight) if constraints else self.max_weight
        
        # Bounds: each weight between min_weight and max_weight
        bounds = tuple((min_w, max_w) for _ in range(n_factors))
        
        # Initial guess: equal weights
        initial_weights = np.array([1.0 / n_factors] * n_factors)
        
        # Optimize
        try:
            result = minimize(
                objective,
                initial_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints_list,
                options={'maxiter': 1000, 'ftol': 1e-9}
            )
            
            if not result.success:
                logger.warning(f"Optimization did not converge: {result.message}")
                # Fallback to equal weights
                return self._equal_weight(factor_returns)
            
            # Convert to dictionary
            weights = {factor: float(w) for factor, w in zip(factor_names, result.x)}
            
            # Calculate final Sharpe ratio
            final_sharpe = -result.fun
            logger.info(f"Max Sharpe optimization completed: Sharpe={final_sharpe:.4f}")
            
            return weights
            
        except Exception as e:
            logger.error(f"Sharpe optimization failed: {e}")
            # Fallback to equal weights
            return self._equal_weight(factor_returns)
    
    def calculate_correlation(
        self,
        factor_returns: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate factor correlation matrix.
        
        Identifies highly correlated factors that may be redundant.
        
        Args:
            factor_returns: Factor returns DataFrame
        
        Returns:
            Correlation matrix DataFrame
        """
        if factor_returns.empty:
            raise OptimizerError("Factor returns DataFrame is empty")
        
        correlation_matrix = factor_returns.corr()
        
        # Log highly correlated pairs
        high_corr_pairs = []
        for i in range(len(correlation_matrix.columns)):
            for j in range(i + 1, len(correlation_matrix.columns)):
                corr = correlation_matrix.iloc[i, j]
                if abs(corr) > self.max_correlation:
                    factor1 = correlation_matrix.columns[i]
                    factor2 = correlation_matrix.columns[j]
                    high_corr_pairs.append((factor1, factor2, corr))
        
        if high_corr_pairs:
            logger.warning(
                f"Found {len(high_corr_pairs)} highly correlated factor pairs "
                f"(|corr| > {self.max_correlation})"
            )
            for f1, f2, corr in high_corr_pairs:
                logger.warning(f"  {f1} <-> {f2}: {corr:.4f}")
        
        return correlation_matrix
    
    def dynamic_rebalance(
        self,
        factor_returns: pd.DataFrame,
        method: OptimizationMethod = OptimizationMethod.MAX_SHARPE,
        window_size: int = 60
    ) -> pd.DataFrame:
        """
        Dynamic weight adjustment using rolling window.
        
        Rebalances factor weights periodically based on recent performance.
        
        Args:
            factor_returns: Factor returns DataFrame (index: dates)
            method: Optimization method
            window_size: Rolling window size (trading days)
        
        Returns:
            DataFrame with columns: date, factor_name, weight
        """
        if factor_returns.empty:
            raise OptimizerError("Factor returns DataFrame is empty")
        
        if len(factor_returns) < window_size:
            raise OptimizerError(
                f"Insufficient data: need at least {window_size} periods, "
                f"got {len(factor_returns)}"
            )
        
        logger.info(
            f"Starting dynamic rebalancing with {method.value} method, "
            f"window_size={window_size}"
        )
        
        # Calculate rebalance dates
        rebalance_dates = factor_returns.index[window_size::self.rebalance_frequency]
        
        # Store weights over time
        weight_history = []
        
        for rebalance_date in rebalance_dates:
            # Get rolling window data
            window_end_idx = factor_returns.index.get_loc(rebalance_date)
            window_start_idx = window_end_idx - window_size
            
            window_data = factor_returns.iloc[window_start_idx:window_end_idx]
            
            # Optimize weights for this window
            try:
                weights = self.optimize_weights(window_data, method=method)
                
                # Record weights
                for factor, weight in weights.items():
                    weight_history.append({
                        'date': rebalance_date,
                        'factor': factor,
                        'weight': weight
                    })
                
            except Exception as e:
                logger.error(f"Failed to rebalance on {rebalance_date}: {e}")
                continue
        
        # Convert to DataFrame
        weight_df = pd.DataFrame(weight_history)
        
        logger.info(
            f"Dynamic rebalancing completed: {len(rebalance_dates)} rebalances"
        )
        
        return weight_df
    
    def calculate_combined_factor(
        self,
        factor_values: dict[str, pd.DataFrame],
        weights: dict[str, float]
    ) -> pd.DataFrame:
        """
        Calculate combined factor value from multiple factors.
        
        Combined factor = weighted sum of individual factor values.
        
        Args:
            factor_values: Dict mapping factor_name to DataFrame (columns: symbol, date, value)
            weights: Dict mapping factor_name to weight
        
        Returns:
            DataFrame with combined factor values (columns: symbol, date, value)
        
        Raises:
            OptimizerError: If calculation fails
        """
        if not factor_values:
            raise OptimizerError("No factor values provided")
        
        if not weights:
            raise OptimizerError("No weights provided")
        
        # Validate weights sum to 1.0
        weight_sum = sum(weights.values())
        if not np.isclose(weight_sum, 1.0):
            raise OptimizerError(f"Weights must sum to 1.0, got {weight_sum}")
        
        logger.info(f"Calculating combined factor from {len(factor_values)} factors")
        
        # Initialize combined factor
        combined = None
        
        for factor_name, weight in weights.items():
            if factor_name not in factor_values:
                logger.warning(f"Factor {factor_name} not found in factor_values, skipping")
                continue
            
            factor_df = factor_values[factor_name].copy()
            
            # Validate required columns
            required_cols = ['symbol', 'date', 'value']
            if not all(col in factor_df.columns for col in required_cols):
                raise OptimizerError(
                    f"Factor {factor_name} missing required columns: {required_cols}"
                )
            
            # Weight the factor values
            factor_df['weighted_value'] = factor_df['value'] * weight
            
            if combined is None:
                combined = factor_df[['symbol', 'date', 'weighted_value']].copy()
            else:
                # Merge with existing combined factor
                combined = combined.merge(
                    factor_df[['symbol', 'date', 'weighted_value']],
                    on=['symbol', 'date'],
                    how='outer',
                    suffixes=('', '_new')
                )
                
                # Sum weighted values
                value_cols = [c for c in combined.columns if 'weighted_value' in c]
                combined['weighted_value'] = combined[value_cols].sum(axis=1)
                
                # Keep only necessary columns
                combined = combined[['symbol', 'date', 'weighted_value']]
        
        if combined is None:
            raise OptimizerError("Failed to calculate combined factor")
        
        # Rename to 'value' for consistency
        combined = combined.rename(columns={'weighted_value': 'value'})
        
        # Remove rows with NaN values
        combined = combined.dropna(subset=['value'])
        
        logger.info(f"Combined factor calculated: {len(combined)} rows")
        
        return combined
    
    def save_combination(
        self,
        user_id: str,
        combination_name: str,
        factor_weights: dict[str, float],
        optimization_method: str,
        description: Optional[str] = None
    ) -> str:
        """
        Save factor combination to database.
        
        Args:
            user_id: User ID
            combination_name: Combination name
            factor_weights: Dictionary of factor weights
            optimization_method: Optimization method used
            description: Optional description
        
        Returns:
            Combination ID
        
        Raises:
            OptimizerError: If save fails
        """
        try:
            db: AsyncSession = next(get_db_client())
            
            combination = FactorCombination(
                user_id=user_id,
                combination_name=combination_name,
                factor_weights=factor_weights,
                optimization_method=optimization_method,
                description=description,
                is_active=True
            )
            
            db.add(combination)
            db.commit()
            db.refresh(combination)
            
            logger.info(f"Saved factor combination: {combination_name}")
            return str(combination.id)
            
        except Exception as e:
            logger.error(f"Failed to save combination: {e}")
            if db:
                db.rollback()
            raise OptimizerError(f"Failed to save combination: {e}")
        finally:
            if db:
                db.close()
    
    def load_combination(self, combination_id: str) -> Optional[FactorCombination]:
        """
        Load factor combination from database.
        
        Args:
            combination_id: Combination ID
        
        Returns:
            FactorCombination or None if not found
        """
        try:
            db: AsyncSession = next(get_db_client())
            combination = db.query(FactorCombination).filter(
                FactorCombination.id == combination_id
            ).first()
            return combination
        except Exception as e:
            logger.error(f"Failed to load combination: {e}")
            return None
        finally:
            if db:
                db.close()
    
    def _validate_weights(self, weights: dict[str, float]) -> None:
        """
        Validate factor weights.
        
        Args:
            weights: Dictionary of weights
        
        Raises:
            OptimizerError: If weights are invalid
        """
        if not weights:
            raise OptimizerError("Weights dictionary is empty")
        
        # Check sum to 1.0
        weight_sum = sum(weights.values())
        if not np.isclose(weight_sum, 1.0, atol=1e-6):
            raise OptimizerError(f"Weights must sum to 1.0, got {weight_sum}")
        
        # Check individual weight bounds
        for factor, weight in weights.items():
            if weight < 0:
                raise OptimizerError(f"Negative weight for {factor}: {weight}")
            if weight > 1.0:
                raise OptimizerError(f"Weight exceeds 1.0 for {factor}: {weight}")

# ============================================
# Global Optimizer Instance
# ============================================

_factor_optimizer: Optional[FactorOptimizer] = None

def get_factor_optimizer(
    lookback_period: int = 252,
    rebalance_frequency: int = 20,
    timeout: int = 30
) -> FactorOptimizer:
    """
    Get global factor optimizer instance.
    
    Args:
        lookback_period: Historical period for optimization
        rebalance_frequency: Rebalance frequency
        timeout: Optimization timeout
    
    Returns:
        Global factor optimizer instance
    """
    global _factor_optimizer
    if _factor_optimizer is None:
        _factor_optimizer = FactorOptimizer(
            lookback_period=lookback_period,
            rebalance_frequency=rebalance_frequency,
            timeout=timeout
        )
    return _factor_optimizer

