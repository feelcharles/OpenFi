"""
Data Adapter

Provides unified interface for accessing multiple data sources with caching and error handling.
Reads data source configurations from config/fetch_sources.yaml for unified API access.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional
from pathlib import Path
import time

import pandas as pd
import redis
import yaml

from system_core.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

class DataAdapterError(Exception):
    """Raised when data adapter operations fail"""
    pass

class DataAdapter(ABC):
    """
    Abstract base class for data adapters.
    
    All data adapters must implement the fetch methods for their specific data type.
    """
    
    def __init__(
        self,
        cache_enabled: bool = True,
        cache_ttl: int = 3600,
        timeout: int = 30,
        retry_attempts: int = 3,
        retry_delay: int = 1
    ):
        """
        Initialize data adapter.
        
        Args:
            cache_enabled: Enable caching
            cache_ttl: Cache TTL in seconds
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        
        # Initialize cache if enabled
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
            except Exception as e:
                logger.warning(f"Failed to connect to Redis cache: {e}")
                self._cache = None
    
    @abstractmethod
    def fetch_data(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch data from the data source.
        
        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters
        
        Returns:
            DataFrame with fetched data
        """
        pass
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        return ":".join(key_parts)
    
    def _get_from_cache(self, cache_key: str) -> Optional[pd.DataFrame]:
        """Get data from cache."""
        if not self.cache_enabled or self._cache is None:
            return None
        
        try:
            cached_data = self._cache.get(cache_key)
            if cached_data:
                # Deserialize DataFrame
                import pickle
                df = pickle.loads(cached_data)
                logger.debug(f"Cache hit: {cache_key}")
                return df
        except Exception as e:
            logger.warning(f"Failed to get from cache: {e}")
        
        return None
    
    def _set_to_cache(self, cache_key: str, data: pd.DataFrame) -> None:
        """Set data to cache."""
        if not self.cache_enabled or self._cache is None:
            return
        
        try:
            # Serialize DataFrame
            import pickle
            serialized = pickle.dumps(data)
            self._cache.setex(cache_key, self.cache_ttl, serialized)
            logger.debug(f"Cached data: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to set cache: {e}")
    
    def _retry_operation(self, operation, *args, **kwargs):
        """Retry operation with exponential backoff."""
        last_exception = None
        
        for attempt in range(self.retry_attempts):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.retry_attempts - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
        
        raise DataAdapterError(
            f"Operation failed after {self.retry_attempts} attempts: {last_exception}"
        )

class MarketDataAdapter(DataAdapter):
    """
    Market data adapter.
    
    Fetches market data (OHLCV) from existing fetch engine.
    """
    
    def __init__(self, **kwargs):
        """Initialize market data adapter."""
        super().__init__(**kwargs)
        # Import here to avoid circular dependency
        from system_core.fetch_engine import DataFetcher
        self.fetcher = DataFetcher()
    
    def fetch_data(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        timeframe: str = '1d',
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch market data.
        
        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            timeframe: Timeframe (e.g., '1d', '1h')
        
        Returns:
            DataFrame with columns: symbol, date, open, high, low, close, volume
        """
        # Check cache
        cache_key = self._get_cache_key(
            'market_data',
            ','.join(sorted(symbols)),
            start_date.isoformat(),
            end_date.isoformat(),
            timeframe
        )
        
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            return cached_data
        
        # Fetch data with retry
        def fetch_operation():
            all_data = []
            
            for symbol in symbols:
                try:
                    # Use existing fetch engine
                    data = self.fetcher.fetch_market_data(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        timeframe=timeframe
                    )
                    
                    if not data.empty:
                        data['symbol'] = symbol
                        all_data.append(data)
                
                except Exception as e:
                    logger.error(f"Failed to fetch data for {symbol}: {e}")
            
            if not all_data:
                return pd.DataFrame()
            
            result = pd.concat(all_data, ignore_index=True)
            
            # Ensure required columns
            required_cols = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in result.columns:
                    result[col] = None
            
            return result[required_cols]
        
        try:
            data = self._retry_operation(fetch_operation)
            
            # Cache result
            if not data.empty:
                self._set_to_cache(cache_key, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            return pd.DataFrame()

class NewsDataAdapter(DataAdapter):
    """
    News data adapter.
    
    Fetches news data from existing fetch engine.
    """
    
    def __init__(self, **kwargs):
        """Initialize news data adapter."""
        super().__init__(**kwargs)
        from system_core.fetch_engine import DataFetcher
        self.fetcher = DataFetcher()
    
    def fetch_data(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch news data.
        
        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
        
        Returns:
            DataFrame with columns: symbol, date, title, content, sentiment
        """
        # Check cache
        cache_key = self._get_cache_key(
            'news_data',
            ','.join(sorted(symbols)),
            start_date.isoformat(),
            end_date.isoformat()
        )
        
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            return cached_data
        
        # Fetch data with retry
        def fetch_operation():
            all_data = []
            
            for symbol in symbols:
                try:
                    data = self.fetcher.fetch_news(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if not data.empty:
                        data['symbol'] = symbol
                        all_data.append(data)
                
                except Exception as e:
                    logger.error(f"Failed to fetch news for {symbol}: {e}")
            
            if not all_data:
                return pd.DataFrame()
            
            result = pd.concat(all_data, ignore_index=True)
            return result
        
        try:
            data = self._retry_operation(fetch_operation)
            
            # Cache result
            if not data.empty:
                self._set_to_cache(cache_key, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch news data: {e}")
            return pd.DataFrame()

class DataAdapterFactory:
    """
    Factory for creating data adapters.
    
    Reads data source configurations from config/fetch_sources.yaml to ensure
    unified API access across all modules (fetch engine, factor system, etc.).
    """
    
    _adapters: dict[str, DataAdapter] = {}
    _config: Optional[dict] = None
    
    @classmethod
    def load_config(cls, config_path: str = "config/fetch_sources.yaml") -> dict:
        """
        Load data source configuration from fetch_sources.yaml.
        
        Args:
            config_path: Path to fetch_sources.yaml
        
        Returns:
            Configuration dictionary
        """
        if cls._config is not None:
            return cls._config
        
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            cls._config = {"sources": []}
            return cls._config
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cls._config = yaml.safe_load(f)
            logger.info(f"Loaded data source config from {config_path}")
            return cls._config
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            cls._config = {"sources": []}
            return cls._config
    
    @classmethod
    def get_source_config(cls, source_id: str) -> Optional[dict]:
        """
        Get configuration for a specific data source.
        
        Args:
            source_id: Source identifier (e.g., 'factor_market_data')
        
        Returns:
            Source configuration or None if not found
        """
        config = cls.load_config()
        sources = config.get("sources", [])
        
        for source in sources:
            if source.get("source_id") == source_id:
                return source
        
        logger.warning(f"Data source not found in config: {source_id}")
        return None
    
    @classmethod
    def get_adapter(cls, adapter_type: str, **config) -> DataAdapter:
        """
        Get or create data adapter.
        
        Automatically reads configuration from fetch_sources.yaml based on adapter type.
        
        Args:
            adapter_type: Type of adapter ('market_data', 'news_data', 'fundamental_data', etc.)
            **config: Optional override configuration
        
        Returns:
            Data adapter instance
        """
        if adapter_type in cls._adapters:
            return cls._adapters[adapter_type]
        
        # Map adapter types to source IDs in fetch_sources.yaml
        source_id_map = {
            'market_data': 'factor_market_data',
            'news_data': 'newsapi_finance',  # Use existing news API
            'fundamental_data': 'factor_fundamental_data',
            'alternative_data': 'factor_alternative_data',
            'economic_data': 'factor_economic_data',
            'options_data': 'factor_options_data'
        }
        
        source_id = source_id_map.get(adapter_type)
        if source_id:
            # Load configuration from fetch_sources.yaml
            source_config = cls.get_source_config(source_id)
            if source_config:
                # Extract cache settings
                cache_config = source_config.get('cache', {})
                adapter_config = {
                    'cache_enabled': cache_config.get('enabled', True),
                    'cache_ttl': cache_config.get('ttl', 3600),
                    'timeout': source_config.get('timeout', 30),
                    'retry_attempts': source_config.get('retry_count', 3),
                    'retry_delay': 1
                }
                # Merge with provided config (provided config takes precedence)
                adapter_config.update(config)
                config = adapter_config
                
                logger.info(
                    f"Creating adapter '{adapter_type}' with config from "
                    f"fetch_sources.yaml (source_id: {source_id})"
                )
        
        # Create adapter based on type
        if adapter_type == 'market_data':
            adapter = MarketDataAdapter(**config)
        elif adapter_type == 'news_data':
            adapter = NewsDataAdapter(**config)
        elif adapter_type in ['fundamental_data', 'alternative_data', 'economic_data', 'options_data']:
            # For new factor data types, use a generic adapter
            adapter = FactorDataAdapter(adapter_type, **config)
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")
        
        cls._adapters[adapter_type] = adapter
        return adapter
    
    @classmethod
    def clear_adapters(cls):
        """Clear all cached adapters."""
        cls._adapters.clear()
    
    @classmethod
    def reload_config(cls):
        """Reload configuration from fetch_sources.yaml."""
        cls._config = None
        cls.load_config()

class FactorDataAdapter(DataAdapter):
    """
    Generic adapter for factor-specific data sources.
    
    This adapter reads configuration from fetch_sources.yaml and provides
    a unified interface for accessing factor data (fundamental, alternative, economic, options).
    """
    
    def __init__(self, data_type: str, **kwargs):
        """
        Initialize factor data adapter.
        
        Args:
            data_type: Type of factor data (fundamental_data, alternative_data, etc.)
            **kwargs: Adapter configuration
        """
        super().__init__(**kwargs)
        self.data_type = data_type
        
        # Get source configuration from fetch_sources.yaml
        source_id_map = {
            'fundamental_data': 'factor_fundamental_data',
            'alternative_data': 'factor_alternative_data',
            'economic_data': 'factor_economic_data',
            'options_data': 'factor_options_data'
        }
        
        source_id = source_id_map.get(data_type)
        self.source_config = DataAdapterFactory.get_source_config(source_id) if source_id else None
        
        if self.source_config:
            logger.info(
                f"Initialized {data_type} adapter with source: "
                f"{self.source_config.get('source_id')}"
            )
    
    def fetch_data(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch factor data from configured source.
        
        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            **kwargs: Additional parameters
        
        Returns:
            DataFrame with fetched data
        """
        # Check cache
        cache_key = self._get_cache_key(
            self.data_type,
            ','.join(sorted(symbols)),
            start_date.isoformat(),
            end_date.isoformat()
        )
        
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            return cached_data
        
        # If no source config, return empty DataFrame
        if not self.source_config:
            logger.warning(
                f"No source configuration found for {self.data_type}, "
                f"returning empty DataFrame"
            )
            return pd.DataFrame()
        
        # Check if source is enabled
        if not self.source_config.get('enabled', False):
            logger.info(
                f"Data source {self.source_config.get('source_id')} is disabled, "
                f"returning empty DataFrame"
            )
            return pd.DataFrame()
        
        # Fetch data with retry
        def fetch_operation():
            # TODO: Implement actual API calls based on source_config
            # For now, return empty DataFrame as placeholder
            # In production, this would call the actual API endpoint
            # specified in fetch_sources.yaml
            
            api_endpoint = self.source_config.get('api_endpoint')
            credentials = self.source_config.get('credentials', {})
            parameters = self.source_config.get('parameters', {})
            
            logger.info(
                f"Fetching {self.data_type} from {api_endpoint} "
                f"for symbols: {symbols}"
            )
            
            # Placeholder: In production, implement actual API call here
            # Example:
            # response = requests.get(
            #     api_endpoint,
            #     headers={'Authorization': f"Bearer {credentials.get('api_key')}"},
            #     params={'symbols': symbols, 'start': start_date, 'end': end_date, **parameters},
            #     timeout=self.timeout
            # )
            # data = parse_response(response)
            
            return pd.DataFrame()
        
        try:
            data = self._retry_operation(fetch_operation)
            
            # Cache result
            if not data.empty:
                self._set_to_cache(cache_key, data)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch {self.data_type}: {e}")
            return pd.DataFrame()
