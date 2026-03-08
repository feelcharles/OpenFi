"""
Factor Screening Module

Provides functionality for:
- Single factor and multi-factor screening
- Factor value sorting and Top N selection
- Factor value normalization (Z-score, MinMax, Rank)
- Industry neutralization
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Any

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.factor_system.engine import FactorEngine, get_factor_engine
from system_core.factor_system.models import Factor, FactorValue, ScreeningPreset
from system_core.database import get_db_client

logger = logging.getLogger(__name__)

class NormalizationMethod(str, Enum):
    """Factor value normalization methods"""
    ZSCORE = "zscore"
    MINMAX = "minmax"
    RANK = "rank"

class ScreeningError(Exception):
    """Raised when screening operation fails"""
    pass

class FactorScreening:
    """
    Factor Screening Engine
    
    Filters and ranks stocks based on factor values with support for:
    - Single and multi-factor screening
    - Top N selection
    - Factor value normalization
    - Industry neutralization
    """
    
    def __init__(
        self,
        factor_engine: Optional[FactorEngine] = None,
        timeout: int = 3
    ):
        """
        Initialize Factor Screening.
        
        Args:
            factor_engine: Factor engine instance
            timeout: Screening timeout in seconds
        """
        self.factor_engine = factor_engine or get_factor_engine()
        self.timeout = timeout
    
    def screen_by_factor(
        self,
        factor_id: str,
        symbols: list[str],
        date: datetime,
        top_n: Optional[int] = None,
        threshold: Optional[float] = None,
        ascending: bool = False,
        normalization: Optional[NormalizationMethod] = None,
        industry_neutral: bool = False,
        industry_data: Optional[dict[str, str]] = None
    ) -> list[tuple[str, float, int]]:
        """
        Screen stocks by single factor.
        
        Args:
            factor_id: Factor identifier
            symbols: List of symbols to screen
            date: Screening date
            top_n: Select top N stocks (mutually exclusive with threshold)
            threshold: Minimum factor value threshold (mutually exclusive with top_n)
            ascending: Sort in ascending order (default: descending)
            normalization: Normalization method to apply
            industry_neutral: Apply industry neutralization
            industry_data: Dict mapping symbol to industry (required if industry_neutral=True)
        
        Returns:
            List of tuples (symbol, factor_value, rank)
        
        Raises:
            ScreeningError: If screening fails
        """
        if top_n is not None and threshold is not None:
            raise ScreeningError("Cannot specify both top_n and threshold")
        
        if industry_neutral and not industry_data:
            raise ScreeningError("industry_data required when industry_neutral=True")
        
        try:
            # Get factor values from database
            factor_values = self._get_factor_values(factor_id, symbols, date)
            
            if factor_values.empty:
                logger.warning(f"No factor values found for {factor_id} on {date.date()}")
                return []
            
            # Add industry data if needed
            if industry_neutral and industry_data:
                factor_values['industry'] = factor_values['symbol'].map(industry_data)
            
            # Normalize if requested
            if normalization:
                factor_values = self._normalize_factor_values(
                    factor_values,
                    method=normalization,
                    industry_neutral=industry_neutral
                )
            
            # Sort by factor value
            factor_values = factor_values.sort_values('value', ascending=ascending)
            
            # Apply filtering
            if top_n is not None:
                factor_values = factor_values.head(top_n)
            elif threshold is not None:
                if ascending:
                    factor_values = factor_values[factor_values['value'] <= threshold]
                else:
                    factor_values = factor_values[factor_values['value'] >= threshold]
            
            # Add rank
            factor_values['rank'] = range(1, len(factor_values) + 1)
            
            # Convert to list of tuples
            results = [
                (row['symbol'], float(row['value']), int(row['rank']))
                for _, row in factor_values.iterrows()
            ]
            
            logger.info(
                f"Screened {len(results)} stocks by factor {factor_id} "
                f"on {date.date()}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Screening failed for factor {factor_id}: {e}")
            raise ScreeningError(f"Screening failed: {e}")
    
    def screen_by_factors(
        self,
        factor_ids: list[str],
        weights: list[float],
        symbols: list[str],
        date: datetime,
        top_n: Optional[int] = None,
        threshold: Optional[float] = None,
        ascending: bool = False,
        normalization: Optional[NormalizationMethod] = None,
        industry_neutral: bool = False,
        industry_data: Optional[dict[str, str]] = None
    ) -> list[tuple[str, float, int]]:
        """
        Screen stocks by multiple factors with weights.
        
        Combines multiple factors using weighted sum to create a composite score.
        
        Args:
            factor_ids: List of factor identifiers
            weights: List of weights (must sum to 1.0)
            symbols: List of symbols to screen
            date: Screening date
            top_n: Select top N stocks
            threshold: Minimum composite score threshold
            ascending: Sort in ascending order
            normalization: Normalization method to apply to each factor
            industry_neutral: Apply industry neutralization
            industry_data: Dict mapping symbol to industry
        
        Returns:
            List of tuples (symbol, composite_score, rank)
        
        Raises:
            ScreeningError: If screening fails
        """
        if len(factor_ids) != len(weights):
            raise ScreeningError("factor_ids and weights must have same length")
        
        if not np.isclose(sum(weights), 1.0):
            raise ScreeningError(f"Weights must sum to 1.0, got {sum(weights)}")
        
        if top_n is not None and threshold is not None:
            raise ScreeningError("Cannot specify both top_n and threshold")
        
        if industry_neutral and not industry_data:
            raise ScreeningError("industry_data required when industry_neutral=True")
        
        try:
            # Get factor values for all factors
            all_factor_values = {}
            for factor_id in factor_ids:
                factor_values = self._get_factor_values(factor_id, symbols, date)
                
                if factor_values.empty:
                    logger.warning(f"No values for factor {factor_id} on {date.date()}")
                    continue
                
                # Add industry data if needed
                if industry_neutral and industry_data:
                    factor_values['industry'] = factor_values['symbol'].map(industry_data)
                
                # Normalize if requested
                if normalization:
                    factor_values = self._normalize_factor_values(
                        factor_values,
                        method=normalization,
                        industry_neutral=industry_neutral
                    )
                
                all_factor_values[factor_id] = factor_values
            
            if not all_factor_values:
                logger.warning(f"No factor values found for any factor on {date.date()}")
                return []
            
            # Calculate composite score
            composite_scores = self._calculate_composite_score(
                all_factor_values,
                factor_ids,
                weights,
                symbols
            )
            
            if composite_scores.empty:
                return []
            
            # Sort by composite score
            composite_scores = composite_scores.sort_values('value', ascending=ascending)
            
            # Apply filtering
            if top_n is not None:
                composite_scores = composite_scores.head(top_n)
            elif threshold is not None:
                if ascending:
                    composite_scores = composite_scores[composite_scores['value'] <= threshold]
                else:
                    composite_scores = composite_scores[composite_scores['value'] >= threshold]
            
            # Add rank
            composite_scores['rank'] = range(1, len(composite_scores) + 1)
            
            # Convert to list of tuples
            results = [
                (row['symbol'], float(row['value']), int(row['rank']))
                for _, row in composite_scores.iterrows()
            ]
            
            logger.info(
                f"Screened {len(results)} stocks by {len(factor_ids)} factors "
                f"on {date.date()}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Multi-factor screening failed: {e}")
            raise ScreeningError(f"Multi-factor screening failed: {e}")
    
    def apply_filters(
        self,
        symbols: list[str],
        filters: dict[str, Any]
    ) -> list[str]:
        """
        Apply additional filters to symbol list.
        
        Args:
            symbols: List of symbols
            filters: Filter conditions (e.g., industries, market_cap, etc.)
        
        Returns:
            Filtered symbol list
        """
        filtered_symbols = symbols.copy()
        
        # Industry filter
        if 'industries' in filters and 'industry_data' in filters:
            allowed_industries = set(filters['industries'])
            industry_data = filters['industry_data']
            filtered_symbols = [
                s for s in filtered_symbols
                if industry_data.get(s) in allowed_industries
            ]
        
        # Market cap filter
        if 'min_market_cap' in filters and 'market_cap_data' in filters:
            min_cap = filters['min_market_cap']
            market_cap_data = filters['market_cap_data']
            filtered_symbols = [
                s for s in filtered_symbols
                if market_cap_data.get(s, 0) >= min_cap
            ]
        
        if 'max_market_cap' in filters and 'market_cap_data' in filters:
            max_cap = filters['max_market_cap']
            market_cap_data = filters['market_cap_data']
            filtered_symbols = [
                s for s in filtered_symbols
                if market_cap_data.get(s, float('inf')) <= max_cap
            ]
        
        logger.info(
            f"Applied filters: {len(symbols)} -> {len(filtered_symbols)} symbols"
        )
        
        return filtered_symbols
    
    def save_preset(
        self,
        user_id: str,
        preset_name: str,
        factor_conditions: list[dict[str, Any]],
        additional_filters: Optional[dict[str, Any]] = None,
        description: Optional[str] = None
    ) -> str:
        """
        Save screening preset to database.
        
        Args:
            user_id: User ID
            preset_name: Preset name
            factor_conditions: List of factor conditions
            additional_filters: Additional filter conditions
            description: Preset description
        
        Returns:
            Preset ID
        """
        try:
            db: AsyncSession = next(get_db_client())
            
            preset = ScreeningPreset(
                user_id=user_id,
                preset_name=preset_name,
                factor_conditions=factor_conditions,
                additional_filters=additional_filters or {},
                description=description
            )
            
            db.add(preset)
            db.commit()
            db.refresh(preset)
            
            logger.info(f"Saved screening preset: {preset_name}")
            return str(preset.id)
            
        except Exception as e:
            logger.error(f"Failed to save preset: {e}")
            if db:
                db.rollback()
            raise ScreeningError(f"Failed to save preset: {e}")
        finally:
            if db:
                db.close()
    
    def load_preset(self, preset_id: str) -> Optional[ScreeningPreset]:
        """
        Load screening preset from database.
        
        Args:
            preset_id: Preset ID
        
        Returns:
            ScreeningPreset or None if not found
        """
        try:
            db: AsyncSession = next(get_db_client())
            preset = db.query(ScreeningPreset).filter(
                ScreeningPreset.id == preset_id
            ).first()
            return preset
        except Exception as e:
            logger.error(f"Failed to load preset: {e}")
            return None
        finally:
            if db:
                db.close()
    
    def _get_factor_values(
        self,
        factor_id: str,
        symbols: list[str],
        date: datetime
    ) -> pd.DataFrame:
        """
        Get factor values from database.
        
        Args:
            factor_id: Factor identifier
            symbols: List of symbols
            date: Date
        
        Returns:
            DataFrame with columns: symbol, date, value
        """
        try:
            db: AsyncSession = next(get_db_client())
            
            # Get factor
            factor = db.query(Factor).filter(Factor.factor_name == factor_id).first()
            if not factor:
                logger.warning(f"Factor not found: {factor_id}")
                return pd.DataFrame()
            
            # Query factor values
            query = db.query(FactorValue).filter(
                FactorValue.factor_id == factor.id,
                FactorValue.symbol.in_(symbols),
                FactorValue.date == date.date()
            )
            
            factor_values = query.all()
            
            if not factor_values:
                return pd.DataFrame()
            
            # Convert to DataFrame
            data = [
                {
                    'symbol': fv.symbol,
                    'date': fv.date,
                    'value': float(fv.value) if fv.value is not None else np.nan
                }
                for fv in factor_values
            ]
            
            df = pd.DataFrame(data)
            
            # Remove NaN values
            df = df.dropna(subset=['value'])
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to get factor values: {e}")
            return pd.DataFrame()
        finally:
            if db:
                db.close()
    
    def _normalize_factor_values(
        self,
        factor_values: pd.DataFrame,
        method: NormalizationMethod,
        industry_neutral: bool = False
    ) -> pd.DataFrame:
        """
        Normalize factor values.
        
        Args:
            factor_values: DataFrame with columns: symbol, date, value, [industry]
            method: Normalization method
            industry_neutral: Apply industry neutralization
        
        Returns:
            DataFrame with normalized values
        """
        result = factor_values.copy()
        
        if industry_neutral and 'industry' in result.columns:
            # Industry neutralization: normalize within each industry
            for industry in result['industry'].unique():
                if pd.isna(industry):
                    continue
                
                mask = result['industry'] == industry
                values = result.loc[mask, 'value']
                
                if len(values) == 0:
                    continue
                
                normalized = self._apply_normalization(values, method)
                result.loc[mask, 'value'] = normalized
        else:
            # Global normalization
            values = result['value']
            normalized = self._apply_normalization(values, method)
            result['value'] = normalized
        
        return result
    
    def _apply_normalization(
        self,
        values: pd.Series,
        method: NormalizationMethod
    ) -> pd.Series:
        """
        Apply normalization method to values.
        
        Args:
            values: Series of values
            method: Normalization method
        
        Returns:
            Normalized values
        """
        if method == NormalizationMethod.ZSCORE:
            # Z-score: (x - mean) / std
            mean = values.mean()
            std = values.std()
            if std == 0:
                return pd.Series(0, index=values.index)
            return (values - mean) / std
        
        elif method == NormalizationMethod.MINMAX:
            # MinMax: (x - min) / (max - min)
            min_val = values.min()
            max_val = values.max()
            if max_val == min_val:
                return pd.Series(0.5, index=values.index)
            return (values - min_val) / (max_val - min_val)
        
        elif method == NormalizationMethod.RANK:
            # Rank: percentile ranking
            return values.rank(pct=True)
        
        else:
            raise ScreeningError(f"Unknown normalization method: {method}")
    
    def _calculate_composite_score(
        self,
        all_factor_values: dict[str, pd.DataFrame],
        factor_ids: list[str],
        weights: list[float],
        symbols: list[str]
    ) -> pd.DataFrame:
        """
        Calculate composite score from multiple factors.
        
        Args:
            all_factor_values: Dict mapping factor_id to DataFrame
            factor_ids: List of factor identifiers
            weights: List of weights
            symbols: List of symbols
        
        Returns:
            DataFrame with columns: symbol, value (composite score)
        """
        # Initialize composite scores
        composite = pd.DataFrame({'symbol': symbols})
        composite['value'] = 0.0
        
        # Add weighted factor values
        for factor_id, weight in zip(factor_ids, weights):
            if factor_id not in all_factor_values:
                continue
            
            factor_df = all_factor_values[factor_id][['symbol', 'value']].copy()
            factor_df['value'] = factor_df['value'] * weight
            
            # Merge with composite
            composite = composite.merge(
                factor_df,
                on='symbol',
                how='left',
                suffixes=('', '_factor')
            )
            
            # Add to composite score (fill NaN with 0)
            composite['value'] = composite['value'] + composite['value_factor'].fillna(0)
            composite = composite.drop(columns=['value_factor'])
        
        # Remove symbols with no factor values
        composite = composite[composite['value'] != 0.0]
        
        return composite

# ============================================
# Global Screening Instance
# ============================================

_factor_screening: Optional[FactorScreening] = None

def get_factor_screening(timeout: int = 3) -> FactorScreening:
    """
    Get global factor screening instance.
    
    Args:
        timeout: Screening timeout in seconds
    
    Returns:
        Global factor screening instance
    """
    global _factor_screening
    if _factor_screening is None:
        _factor_screening = FactorScreening(timeout=timeout)
    return _factor_screening

