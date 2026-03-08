"""
Database client for OpenFi Lite system.

This module provides database connection management, connection pooling,
and retry mechanisms for database operations.
"""

import asyncio
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

import redis.asyncio as redis
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.exc import OperationalError, DBAPIError

from system_core.config.settings import get_settings

logger = logging.getLogger(__name__)

class DatabaseClient:
    """
    Async database client with connection pooling and retry mechanisms.
    
    Features:
    - Connection pooling (min 5, max 20 connections)
    - Automatic retry on transient failures (max 2 retries)
    - Context manager support for transactions
    - Redis caching for frequently accessed queries (TTL 300s)
    """
    
    def __init__(
        self,
        database_url: Optional[str] = None,
        redis_url: Optional[str] = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
        echo: bool = False,
        cache_ttl: int = 300,  # 5 minutes default TTL
        cache_enabled: bool = True,
    ):
        """
        Initialize database client.
        
        Args:
            database_url: PostgreSQL connection URL (defaults to settings)
            redis_url: Redis connection URL for caching (defaults to settings)
            pool_size: Maximum number of connections in the pool (default: 10)
            max_overflow: Maximum overflow connections beyond pool_size (default: 20)
            pool_timeout: Timeout in seconds for getting connection from pool (default: 30)
            pool_recycle: Recycle connections after this many seconds (default: 3600)
            pool_pre_ping: Enable connection health checks (default: True)
            echo: Enable SQL query logging (default: False)
            cache_ttl: Cache TTL in seconds (default: 300)
            cache_enabled: Enable Redis caching (default: True)
        """
        if database_url is None:
            settings = get_settings()
            self.database_url = settings.database_url
        else:
            self.database_url = database_url
        
        if redis_url is None:
            settings = get_settings()
            self.redis_url = getattr(settings, 'redis_url', 'redis://localhost:6379/0')
        else:
            self.redis_url = redis_url
        
        # Create async engine with connection pooling
        self.engine = create_async_engine(
            self.database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping,
            echo=echo,
        )
        
        # Create session factory
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        self.max_retries = 2
        self.retry_delay = 1.0  # seconds
        
        # Redis cache configuration
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self.redis_client: Optional[redis.Redis] = None
        
        if self.cache_enabled:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                logger.info(f"Redis cache enabled with TTL={cache_ttl}s")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis cache: {e}. Caching disabled.")
                self.cache_enabled = False
        
        logger.info(
            f"Database client initialized with pool_size={pool_size}, "
            f"max_overflow={max_overflow}, pool_timeout={pool_timeout}, "
            f"pool_recycle={pool_recycle}, max_retries={self.max_retries}, "
            f"cache_enabled={self.cache_enabled}"
        )
    
    async def initialize(self):
        """
        Initialize database client and verify connection.
        
        This method performs health checks and schema validation.
        """
        if not await self.health_check():
            raise RuntimeError("Failed to connect to database")
        logger.info("Database client initialized successfully")
    
    @asynccontextmanager
    async def session(self):
        """
        Async context manager for database sessions.
        
        Usage:
            async with db_client.session() as session:
                result = await session.execute(query)
        """
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Session error, rolling back: {e}")
                raise
            finally:
                await session.close()
    
    def get_session(self):
        """
        Get database session context manager.
        
        This is an alias for session() for backward compatibility.
        
        Usage:
            async with db_client.get_session() as session:
                result = await session.execute(query)
        
        Returns:
            Async context manager for database session
        """
        return self.session()
    
    def _generate_cache_key(self, query: str, params: Optional[dict[str, Any]] = None) -> str:
        """
        Generate cache key from query and parameters.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Cache key string
        """
        # Create a deterministic hash of query + params
        cache_data = {
            "query": query.strip(),
            "params": params or {}
        }
        cache_str = json.dumps(cache_data, sort_keys=True)
        cache_hash = hashlib.sha256(cache_str.encode()).hexdigest()
        return f"db:query:{cache_hash}"
    
    async def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """
        Get query result from Redis cache.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached result or None
        """
        if not self.cache_enabled or not self.redis_client:
            return None
        
        try:
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for key: {cache_key}")
                return json.loads(cached_data)
            logger.debug(f"Cache miss for key: {cache_key}")
            return None
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    async def _set_in_cache(self, cache_key: str, data: Any) -> None:
        """
        Store query result in Redis cache.
        
        Args:
            cache_key: Cache key
            data: Data to cache
        """
        if not self.cache_enabled or not self.redis_client:
            return
        
        try:
            cached_data = json.dumps(data, default=str)
            await self.redis_client.setex(cache_key, self.cache_ttl, cached_data)
            logger.debug(f"Cached data for key: {cache_key}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    async def execute_with_retry(
        self,
        query: str,
        params: Optional[dict[str, Any]] = None,
        fetch_one: bool = False,
        fetch_all: bool = False,
        use_cache: bool = True,
    ) -> Optional[Any]:
        """
        Execute a query with automatic retry on transient failures and optional caching.
        
        Args:
            query: SQL query string
            params: Query parameters
            fetch_one: Return single row result
            fetch_all: Return all rows result
            use_cache: Use Redis cache for read queries (default: True)
            
        Returns:
            Query result or None
            
        Raises:
            Exception: After max retries exhausted
        """
        # Check cache for SELECT queries
        if use_cache and query.strip().upper().startswith('SELECT'):
            cache_key = self._generate_cache_key(query, params)
            cached_result = await self._get_from_cache(cache_key)
            if cached_result is not None:
                return cached_result
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                async with self.session() as session:
                    result = await session.execute(text(query), params or {})
                    
                    if fetch_one:
                        row = result.fetchone()
                        result_data = dict(row._mapping) if row else None
                    elif fetch_all:
                        rows = result.fetchall()
                        result_data = [dict(row._mapping) for row in rows]
                    else:
                        result_data = None
                    
                    # Cache SELECT query results
                    if use_cache and query.strip().upper().startswith('SELECT') and result_data is not None:
                        cache_key = self._generate_cache_key(query, params)
                        await self._set_in_cache(cache_key, result_data)
                    
                    return result_data
                        
            except (OperationalError, DBAPIError) as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        f"Database operation failed (attempt {attempt + 1}/{self.max_retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"Database operation failed after {self.max_retries + 1} attempts: {e}"
                    )
                    raise
            except Exception as e:
                # Non-retryable error
                logger.error(f"Non-retryable database error: {e}")
                raise
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
    
    async def health_check(self) -> bool:
        """
        Check database connection health.
        
        Returns:
            True if database is accessible, False otherwise
        """
        try:
            async with self.session() as session:
                await session.execute(text("SELECT 1"))
            logger.info("Database health check passed")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def validate_schema(self) -> bool:
        """
        Validate that database schema matches the models.
        
        This checks for the existence of critical tables and returns True if
        the schema appears valid, False otherwise.
        
        Returns:
            True if schema is valid, False otherwise
        """
        try:
            async with self.session() as session:
                # Check for critical tables
                critical_tables = [
                    'users', 'ea_profiles', 'trades', 'brokers', 
                    'trading_accounts', 'signals', 'notifications',
                    'alert_rules', 'circuit_breaker_states', 'audit_logs'
                ]
                
                for table_name in critical_tables:
                    result = await session.execute(
                        text(
                            "SELECT EXISTS ("
                            "SELECT FROM information_schema.tables "
                            "WHERE table_schema = 'public' "
                            f"AND table_name = '{table_name}'"
                            ")"
                        )
                    )
                    exists = result.scalar()
                    
                    if not exists:
                        logger.error(f"Schema validation failed: table '{table_name}' does not exist")
                        return False
                
                logger.info("Database schema validation passed")
                return True
                
        except Exception as e:
            logger.error(f"Schema validation error: {e}")
            return False
    
    async def close(self):
        """Close database engine and all connections."""
        await self.engine.dispose()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Database client closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

# Global database client instance
_db_client: Optional[DatabaseClient] = None

def get_db_client() -> DatabaseClient:
    """
    Get or create global database client instance.
    
    Returns:
        DatabaseClient instance
    """
    global _db_client
    
    if _db_client is None:
        _db_client = DatabaseClient()
    
    return _db_client

async def init_db():
    """Initialize database client and verify connection and schema."""
    db_client = get_db_client()
    
    if not await db_client.health_check():
        raise RuntimeError("Failed to connect to database")
    
    if not await db_client.validate_schema():
        logger.warning(
            "Database schema validation failed. "
            "Please run 'alembic upgrade head' to apply migrations."
        )
    
    logger.info("Database initialized successfully")

async def close_db():
    """Close database client and cleanup resources."""
    global _db_client
    
    if _db_client is not None:
        await _db_client.close()
        _db_client = None
        logger.info("Database closed")

async def get_db():
    """
    Get database session for FastAPI dependency injection.
    
    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    
    Yields:
        AsyncSession: Database session
    """
    db_client = get_db_client()
    async with db_client.session() as session:
        yield session

@asynccontextmanager
async def get_session():
    """
    Get database session as async context manager.
    
    This is an alias for get_db_client().session() for backward compatibility.
    
    Usage:
        async with get_session() as session:
            result = await session.execute(query)
    
    Yields:
        AsyncSession: Database session
    """
    db_client = get_db_client()
    async with db_client.session() as session:
        yield session
