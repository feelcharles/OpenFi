"""
Global Data Cache Layer

Provides unified caching for market data, news, and other frequently accessed data.
Prevents duplicate fetches and improves performance across modules.

Requirements: Performance optimization
"""

import hashlib
import logging
import pickle
from datetime import datetime, timedelta
from typing import Any, Optional, Callable
import pandas as pd
import redis

logger = logging.getLogger(__name__)

class CacheEntry:
    """Cache entry with metadata"""
    
    def __init__(self, data: Any, ttl: int):
        """
        Initialize cache entry.
        
        Args:
            data: Data to cache
            ttl: Time to live in seconds
        """
        self.data = data
        self.created_at = datetime.utcnow()
        self.ttl = ttl
        self.access_count = 0
        self.last_accessed = self.created_at
    
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl
    
    def access(self) -> Any:
        """Access cached data and update metadata."""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()
        return self.data

class GlobalDataCache:
    """
    Global data cache for market data, news, and other frequently accessed data.
    
    Uses Redis for distributed caching with fallback to in-memory cache.
    Implements cache-aside pattern with automatic expiration.
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/1",
        default_ttl: int = 3600,
        enable_redis: bool = True
    ):
        """
        Initialize global data cache.
        
        Args:
            redis_url: Redis connection URL
            default_ttl: Default TTL in seconds (1 hour)
            enable_redis: Enable Redis caching
        """
        self.default_ttl = default_ttl
        self.enable_redis = enable_redis
        
        # Redis client
        self.redis_client: Optional[redis.Redis] = None
        if enable_redis:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=False)
                self.redis_client.ping()
                logger.info("Connected to Redis for global data cache")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}, using in-memory cache")
                self.redis_client = None
        
        # In-memory fallback cache
        self._memory_cache: dict[str, CacheEntry] = {}
        
        # Cache statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'evictions': 0,
        }
    
    def get(
        self,
        key: str,
        fetch_func: Optional[Callable[[], Any]] = None,
        ttl: Optional[int] = None
    ) -> Optional[Any]:
        """
        Get data from cache or fetch if not cached.
        
        Args:
            key: Cache key
            fetch_func: Function to fetch data if not cached (optional)
            ttl: TTL for new cache entry (uses default if None)
        
        Returns:
            Cached or fetched data, or None if not found and no fetch function
        """
        # Try to get from cache
        cached_data = self._get_from_cache(key)
        
        if cached_data is not None:
            self._stats['hits'] += 1
            logger.debug(f"Cache hit: {key}")
            return cached_data
        
        self._stats['misses'] += 1
        logger.debug(f"Cache miss: {key}")
        
        # Fetch data if function provided
        if fetch_func is not None:
            try:
                data = fetch_func()
                if data is not None:
                    self.set(key, data, ttl)
                return data
            except Exception as e:
                logger.error(f"Failed to fetch data for cache key {key}: {e}")
                return None
        
        return None
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """
        Set data in cache.
        
        Args:
            key: Cache key
            data: Data to cache
            ttl: TTL in seconds (uses default if None)
        
        Returns:
            True if successful, False otherwise
        """
        ttl = ttl or self.default_ttl
        
        try:
            # Try Redis first
            if self.redis_client is not None:
                serialized = pickle.dumps(data)
                self.redis_client.setex(key, ttl, serialized)
                logger.debug(f"Cached in Redis: {key} (TTL: {ttl}s)")
            else:
                # Fallback to memory cache
                self._memory_cache[key] = CacheEntry(data, ttl)
                logger.debug(f"Cached in memory: {key} (TTL: {ttl}s)")
            
            self._stats['sets'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache data for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete data from cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if deleted, False otherwise
        """
        try:
            if self.redis_client is not None:
                self.redis_client.delete(key)
            
            if key in self._memory_cache:
                del self._memory_cache[key]
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete cache key {key}: {e}")
            return False
    
    def clear(self) -> bool:
        """
        Clear all cached data.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.redis_client is not None:
                self.redis_client.flushdb()
            
            self._memory_cache.clear()
            logger.info("Cleared global data cache")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """
        Get data from cache (Redis or memory).
        
        Args:
            key: Cache key
        
        Returns:
            Cached data or None
        """
        # Try Redis first
        if self.redis_client is not None:
            try:
                cached = self.redis_client.get(key)
                if cached:
                    return pickle.loads(cached)
            except Exception as e:
                logger.warning(f"Failed to get from Redis cache: {e}")
        
        # Try memory cache
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            
            # Check expiration
            if entry.is_expired():
                del self._memory_cache[key]
                self._stats['evictions'] += 1
                return None
            
            return entry.access()
        
        return None
    
    def get_market_data(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        fetch_func: Optional[Callable[[], pd.DataFrame]] = None
    ) -> Optional[pd.DataFrame]:
        """
        Get market data from cache or fetch.
        
        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            fetch_func: Function to fetch data if not cached
        
        Returns:
            DataFrame with market data or None
        """
        key = self._make_market_data_key(symbols, start_date, end_date)
        return self.get(key, fetch_func, ttl=1800)  # 30 minutes TTL
    
    def get_news(
        self,
        keywords: list[str],
        start_date: datetime,
        end_date: datetime,
        fetch_func: Optional[Callable[[], pd.DataFrame]] = None
    ) -> Optional[pd.DataFrame]:
        """
        Get news data from cache or fetch.
        
        Args:
            keywords: List of keywords
            start_date: Start date
            end_date: End date
            fetch_func: Function to fetch data if not cached
        
        Returns:
            DataFrame with news data or None
        """
        key = self._make_news_key(keywords, start_date, end_date)
        return self.get(key, fetch_func, ttl=600)  # 10 minutes TTL
    
    def get_calendar(
        self,
        start_date: datetime,
        end_date: datetime,
        fetch_func: Optional[Callable[[], pd.DataFrame]] = None
    ) -> Optional[pd.DataFrame]:
        """
        Get calendar data from cache or fetch.
        
        Args:
            start_date: Start date
            end_date: End date
            fetch_func: Function to fetch data if not cached
        
        Returns:
            DataFrame with calendar events or None
        """
        key = self._make_calendar_key(start_date, end_date)
        return self.get(key, fetch_func, ttl=3600)  # 1 hour TTL
    
    def _make_market_data_key(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """Generate cache key for market data."""
        symbols_str = ','.join(sorted(symbols))
        date_str = f"{start_date.date()}_{end_date.date()}"
        return f"market_data:{symbols_str}:{date_str}"
    
    def _make_news_key(
        self,
        keywords: list[str],
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """Generate cache key for news data."""
        keywords_str = ','.join(sorted(keywords))
        date_str = f"{start_date.date()}_{end_date.date()}"
        return f"news:{keywords_str}:{date_str}"
    
    def _make_calendar_key(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """Generate cache key for calendar data."""
        date_str = f"{start_date.date()}_{end_date.date()}"
        return f"calendar:{date_str}"
    
    def get_statistics(self) -> dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (
            self._stats['hits'] / total_requests * 100
            if total_requests > 0 else 0
        )
        
        return {
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'sets': self._stats['sets'],
            'evictions': self._stats['evictions'],
            'hit_rate': f"{hit_rate:.2f}%",
            'memory_cache_size': len(self._memory_cache),
            'redis_enabled': self.redis_client is not None,
        }

# Global cache instance
_global_cache: Optional[GlobalDataCache] = None

def get_global_cache() -> GlobalDataCache:
    """
    Get global data cache instance.
    
    Returns:
        Global data cache
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = GlobalDataCache()
    return _global_cache

__all__ = [
    'GlobalDataCache',
    'get_global_cache',
]
