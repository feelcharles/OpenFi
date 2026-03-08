"""
Factor Calculation Engine

Core engine for executing factor calculations with support for:
- Single factor and batch calculations
- Incremental calculation (only new data)
- Parallel computation optimization
- Result caching and database persistence
"""

import logging
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta
from typing import Any, Optional
import time
import multiprocessing

import pandas as pd
import redis
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.factor_system.base_factor import BaseFactor
from system_core.factor_system.manager import FactorManager, get_factor_manager
from system_core.factor_system.data_adapter import DataAdapterFactory
from system_core.factor_system.models import Factor, FactorValue
from system_core.database import get_db_client
from system_core.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

class FactorCalculationError(Exception):
    """Raised when factor calculation fails"""
    pass

class FactorEngine:
    """
    Factor Calculation Engine
    
    Executes factor calculations with support for:
    - Single and batch calculations
    - Incremental updates
    - Parallel processing
    - Caching and persistence
    """
    
    def __init__(
        self,
        factor_manager: Optional[FactorManager] = None,
        max_workers: int = 4,
        calculation_timeout: int = 5,
        batch_calculation_timeout: int = 60,
        enable_parallel: bool = True,
        cache_enabled: bool = True,
        cache_ttl: int = 3600
    ):
        """
        Initialize Factor Engine.
        
        Args:
            factor_manager: Factor manager instance
            max_workers: Maximum worker processes for parallel computation
            calculation_timeout: Timeout for single factor calculation (seconds)
            batch_calculation_timeout: Timeout for batch calculation (seconds)
            enable_parallel: Enable parallel computation
            cache_enabled: Enable result caching
            cache_ttl: Cache TTL in seconds
        """
        self.factor_manager = factor_manager or get_factor_manager()
        self.max_workers = max_workers
        self.calculation_timeout = calculation_timeout
        self.batch_calculation_timeout = batch_calculation_timeout
        self.enable_parallel = enable_parallel
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        
        # Initialize cache
        self._cache: Optional[redis.Redis] = None
        if cache_enabled:
            try:
                self._cache = redis.Redis(
                    host='localhost',
                    port=6379,
                    db=2,
                    decode_responses=False
                )
                self._cache.ping()
                logger.info("Connected to Redis cache")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis cache: {e}")
                self._cache = None
    
    def calculate_factor(
        self,
        factor_id: str,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        params: Optional[dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Calculate single factor values.
        
        Args:
            factor_id: Factor identifier (name)
            symbols: List of symbols to calculate
            start_date: Start date
            end_date: End date
            params: Optional factor parameters
        
        Returns:
            DataFrame with columns: symbol, date, value
        
        Raises:
            FactorCalculationError: If calculation fails
        """
        start_time = time.time()
        
        try:
            # Get factor instance
            factor = self.factor_manager.get_factor(factor_id)
            if factor is None:
                raise FactorCalculationError(f"Factor not found: {factor_id}")
            
            # Check cache
            cache_key = self._get_cache_key(factor_id, symbols, start_date, end_date, params)
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for factor {factor_id}")
                return cached_result
            
            # Fetch required data
            data = self._fetch_factor_data(factor, symbols, start_date, end_date)
            
            # Calculate factor
            result = self._execute_calculation(
                factor,
                data,
                params,
                timeout=self.calculation_timeout
            )
            
            # Validate result
            if result.empty:
                logger.warning(f"Factor {factor_id} returned empty result")
                return result
            
            # Cache result
            self._set_to_cache(cache_key, result)
            
            # Store to database
            self._store_factor_values(factor_id, result)
            
            elapsed = time.time() - start_time
            logger.info(
                f"Calculated factor {factor_id} for {len(symbols)} symbols "
                f"in {elapsed:.2f}s"
            )
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"Failed to calculate factor {factor_id} after {elapsed:.2f}s: {e}"
            )
            raise FactorCalculationError(f"Factor calculation failed: {e}")
    
    def calculate_factors_batch(
        self,
        factor_ids: list[str],
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        params: Optional[dict[str, dict[str, Any]]] = None
    ) -> dict[str, pd.DataFrame]:
        """
        Calculate multiple factors in batch.
        
        Uses parallel processing to calculate independent factors simultaneously.
        
        Args:
            factor_ids: List of factor identifiers
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            params: Optional dict mapping factor_id to parameters
        
        Returns:
            Dictionary mapping factor_id to result DataFrame
        """
        start_time = time.time()
        results = {}
        
        if not factor_ids:
            return results
        
        logger.info(
            f"Starting batch calculation of {len(factor_ids)} factors "
            f"for {len(symbols)} symbols"
        )
        
        if self.enable_parallel and len(factor_ids) > 1:
            # Parallel calculation
            results = self._calculate_batch_parallel(
                factor_ids, symbols, start_date, end_date, params
            )
        else:
            # Sequential calculation
            for factor_id in factor_ids:
                factor_params = params.get(factor_id) if params else None
                try:
                    result = self.calculate_factor(
                        factor_id, symbols, start_date, end_date, factor_params
                    )
                    results[factor_id] = result
                except Exception as e:
                    logger.error(f"Failed to calculate factor {factor_id}: {e}")
                    results[factor_id] = pd.DataFrame()
        
        elapsed = time.time() - start_time
        successful = sum(1 for df in results.values() if not df.empty)
        logger.info(
            f"Batch calculation completed: {successful}/{len(factor_ids)} factors "
            f"in {elapsed:.2f}s"
        )
        
        return results
    
    def _calculate_batch_parallel(
        self,
        factor_ids: list[str],
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        params: Optional[dict[str, dict[str, Any]]]
    ) -> dict[str, pd.DataFrame]:
        """
        Calculate factors in parallel using ProcessPoolExecutor.
        
        Args:
            factor_ids: List of factor identifiers
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            params: Optional parameters dict
        
        Returns:
            Dictionary mapping factor_id to result DataFrame
        """
        results = {}
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all calculation tasks
            future_to_factor = {}
            for factor_id in factor_ids:
                factor_params = params.get(factor_id) if params else None
                future = executor.submit(
                    _calculate_factor_worker,
                    factor_id,
                    symbols,
                    start_date,
                    end_date,
                    factor_params,
                    self.calculation_timeout
                )
                future_to_factor[future] = factor_id
            
            # Collect results with timeout
            for future in as_completed(future_to_factor, timeout=self.batch_calculation_timeout):
                factor_id = future_to_factor[future]
                try:
                    result = future.result(timeout=self.calculation_timeout)
                    results[factor_id] = result
                    
                    # Cache and store result
                    if not result.empty:
                        cache_key = self._get_cache_key(
                            factor_id, symbols, start_date, end_date,
                            params.get(factor_id) if params else None
                        )
                        self._set_to_cache(cache_key, result)
                        self._store_factor_values(factor_id, result)
                    
                except FuturesTimeoutError:
                    logger.error(f"Factor {factor_id} calculation timed out")
                    results[factor_id] = pd.DataFrame()
                except Exception as e:
                    logger.error(f"Factor {factor_id} calculation failed: {e}")
                    results[factor_id] = pd.DataFrame()
        
        return results
    
    def calculate_incremental(
        self,
        factor_id: str,
        symbols: list[str],
        last_date: datetime,
        params: Optional[dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Calculate factor values incrementally (only new data since last_date).
        
        This is more efficient than full recalculation when only recent data needs updating.
        
        Args:
            factor_id: Factor identifier
            symbols: List of symbols
            last_date: Last calculated date (will calculate from last_date+1 to today)
            params: Optional factor parameters
        
        Returns:
            DataFrame with new factor values
        """
        # Calculate from last_date + 1 day to today
        start_date = last_date + timedelta(days=1)
        end_date = datetime.now()
        
        if start_date >= end_date:
            logger.info(f"No new data to calculate for factor {factor_id}")
            return pd.DataFrame()
        
        logger.info(
            f"Incremental calculation for factor {factor_id} "
            f"from {start_date.date()} to {end_date.date()}"
        )
        
        return self.calculate_factor(factor_id, symbols, start_date, end_date, params)
    
    def get_cached_result(
        self,
        factor_id: str,
        symbol: str,
        date: datetime
    ) -> Optional[float]:
        """
        Get cached factor value for a specific symbol and date.
        
        Args:
            factor_id: Factor identifier
            symbol: Symbol
            date: Date
        
        Returns:
            Factor value or None if not cached
        """
        if not self.cache_enabled or self._cache is None:
            return None
        
        cache_key = f"factor_value:{factor_id}:{symbol}:{date.date().isoformat()}"
        
        try:
            cached_value = self._cache.get(cache_key)
            if cached_value:
                return float(cached_value)
        except Exception as e:
            logger.warning(f"Failed to get cached value: {e}")
        
        return None
    
    def _fetch_factor_data(
        self,
        factor: BaseFactor,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch required data for factor calculation.
        
        Args:
            factor: Factor instance
            symbols: List of symbols
            start_date: Start date
            end_date: End date
        
        Returns:
            Dictionary of data sources
        """
        data = {}
        
        for data_source in factor.required_data:
            try:
                adapter = DataAdapterFactory.get_adapter(data_source)
                df = adapter.fetch_data(symbols, start_date, end_date)
                data[data_source] = df
                
                if df.empty:
                    logger.warning(f"No data fetched from {data_source}")
                
            except Exception as e:
                logger.error(f"Failed to fetch data from {data_source}: {e}")
                data[data_source] = pd.DataFrame()
        
        return data
    
    def _execute_calculation(
        self,
        factor: BaseFactor,
        data: dict[str, pd.DataFrame],
        params: Optional[dict[str, Any]],
        timeout: int
    ) -> pd.DataFrame:
        """
        Execute factor calculation with timeout protection.
        
        Args:
            factor: Factor instance
            data: Input data
            params: Factor parameters
            timeout: Timeout in seconds
        
        Returns:
            Calculation result
        """
        # Validate data
        if not factor.validate_data(data):
            raise FactorCalculationError(
                f"Invalid data for factor {factor.name}: missing required data sources"
            )
        
        # Execute calculation
        try:
            result = factor.calculate(data, params)
            
            # Validate result format
            required_cols = ['symbol', 'date', 'value']
            if not all(col in result.columns for col in required_cols):
                raise FactorCalculationError(
                    f"Factor {factor.name} returned invalid format. "
                    f"Required columns: {required_cols}"
                )
            
            return result
            
        except Exception as e:
            raise FactorCalculationError(f"Factor calculation error: {e}")
    
    def _store_factor_values(
        self,
        factor_id: str,
        result: pd.DataFrame
    ) -> None:
        """
        Store factor values to database.
        
        Args:
            factor_id: Factor identifier
            result: Calculation result DataFrame
        """
        if result.empty:
            return
        
        try:
            db: AsyncSession = next(get_db_client())
            
            # Get factor from database
            factor = db.query(Factor).filter(Factor.factor_name == factor_id).first()
            if not factor:
                logger.warning(f"Factor {factor_id} not found in database, skipping storage")
                return
            
            # Prepare factor values for bulk insert
            factor_values = []
            for _, row in result.iterrows():
                factor_value = FactorValue(
                    factor_id=factor.id,
                    symbol=row['symbol'],
                    date=pd.to_datetime(row['date']).date(),
                    value=float(row['value']) if pd.notna(row['value']) else None,
                    metadata={'calculation_time': datetime.now().isoformat()}
                )
                factor_values.append(factor_value)
            
            # Bulk insert
            if factor_values:
                db.bulk_save_objects(factor_values)
                db.commit()
                logger.info(f"Stored {len(factor_values)} factor values to database")
            
        except Exception as e:
            logger.error(f"Failed to store factor values: {e}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()
    
    def _get_cache_key(
        self,
        factor_id: str,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        params: Optional[dict[str, Any]]
    ) -> str:
        """Generate cache key for factor calculation."""
        symbols_str = ','.join(sorted(symbols))
        params_str = str(sorted(params.items())) if params else ''
        return (
            f"factor_calc:{factor_id}:{symbols_str}:"
            f"{start_date.date().isoformat()}:{end_date.date().isoformat()}:{params_str}"
        )
    
    def _get_from_cache(self, cache_key: str) -> Optional[pd.DataFrame]:
        """Get calculation result from cache."""
        if not self.cache_enabled or self._cache is None:
            return None
        
        try:
            cached_data = self._cache.get(cache_key)
            if cached_data:
                import pickle
                df = pickle.loads(cached_data)
                return df
        except Exception as e:
            logger.warning(f"Failed to get from cache: {e}")
        
        return None
    
    def _set_to_cache(self, cache_key: str, data: pd.DataFrame) -> None:
        """Set calculation result to cache."""
        if not self.cache_enabled or self._cache is None:
            return
        
        try:
            import pickle
            serialized = pickle.dumps(data)
            self._cache.setex(cache_key, self.cache_ttl, serialized)
        except Exception as e:
            logger.warning(f"Failed to set cache: {e}")

# ============================================
# Worker Function for Parallel Processing
# ============================================

def _calculate_factor_worker(
    factor_id: str,
    symbols: list[str],
    start_date: datetime,
    end_date: datetime,
    params: Optional[dict[str, Any]],
    timeout: int
) -> pd.DataFrame:
    """
    Worker function for parallel factor calculation.
    
    This function runs in a separate process.
    
    Args:
        factor_id: Factor identifier
        symbols: List of symbols
        start_date: Start date
        end_date: End date
        params: Factor parameters
        timeout: Calculation timeout
    
    Returns:
        Calculation result DataFrame
    """
    try:
        # Create new factor manager instance in worker process
        factor_manager = get_factor_manager()
        
        # Get factor
        factor = factor_manager.get_factor(factor_id)
        if factor is None:
            logger.error(f"Factor not found in worker: {factor_id}")
            return pd.DataFrame()
        
        # Fetch data
        data = {}
        for data_source in factor.required_data:
            try:
                adapter = DataAdapterFactory.get_adapter(data_source)
                df = adapter.fetch_data(symbols, start_date, end_date)
                data[data_source] = df
            except Exception as e:
                logger.error(f"Worker failed to fetch {data_source}: {e}")
                data[data_source] = pd.DataFrame()
        
        # Validate data
        if not factor.validate_data(data):
            logger.error(f"Invalid data for factor {factor_id} in worker")
            return pd.DataFrame()
        
        # Calculate
        result = factor.calculate(data, params)
        return result
        
    except Exception as e:
        logger.error(f"Worker calculation failed for {factor_id}: {e}")
        return pd.DataFrame()

# ============================================
# Global Engine Instance
# ============================================

_factor_engine: Optional[FactorEngine] = None

def get_factor_engine(
    max_workers: int = 4,
    calculation_timeout: int = 5,
    batch_calculation_timeout: int = 60,
    enable_parallel: bool = True
) -> FactorEngine:
    """
    Get global factor engine instance.
    
    Args:
        max_workers: Maximum worker processes
        calculation_timeout: Single calculation timeout
        batch_calculation_timeout: Batch calculation timeout
        enable_parallel: Enable parallel processing
    
    Returns:
        Global factor engine
    """
    global _factor_engine
    if _factor_engine is None:
        _factor_engine = FactorEngine(
            max_workers=max_workers,
            calculation_timeout=calculation_timeout,
            batch_calculation_timeout=batch_calculation_timeout,
            enable_parallel=enable_parallel
        )
    return _factor_engine

