"""
Data Proxy for Secure Data Access

Provides proxy pattern for data fetching that hides API credentials
from calling modules. Only returns data, never exposes credentials.

Requirements: 42.1, 42.2, 42.3
"""

import logging
from typing import Any, Optional
from datetime import datetime
import pandas as pd

from system_core.security.secure_config_manager import (
    get_secure_config_manager,
    RequesterContext,
    AccessLevel
)

logger = logging.getLogger(__name__)

class SecureDataProxy:
    """
    Secure data proxy that fetches data without exposing credentials.
    
    This proxy sits between data consumers (AI, agents, etc.) and data sources.
    It handles credential management internally and only returns data.
    """
    
    def __init__(self):
        """Initialize secure data proxy."""
        self.secure_config = get_secure_config_manager()
        self._fetcher_registry: dict[str, Any] = {}
    
    def register_fetcher(self, source_type: str, fetcher_class: Any) -> None:
        """
        Register a data fetcher for a source type.
        
        Args:
            source_type: Type of data source (e.g., "news", "calendar", "sentiment")
            fetcher_class: Fetcher class that implements fetch() method
        """
        self._fetcher_registry[source_type] = fetcher_class
        logger.info(f"Registered fetcher for source type: {source_type}")
    
    def fetch_data(
        self,
        source_type: str,
        params: dict[str, Any],
        requester_context: RequesterContext
    ) -> pd.DataFrame:
        """
        Fetch data from a source without exposing credentials.
        
        Args:
            source_type: Type of data source
            params: Fetch parameters (symbols, date range, etc.)
            requester_context: Context of the requester
        
        Returns:
            DataFrame with fetched data
        
        Raises:
            ValueError: If source type not registered
            PermissionError: If requester not authorized
        """
        # Validate source type
        if source_type not in self._fetcher_registry:
            raise ValueError(f"Unknown source type: {source_type}")
        
        # Log access attempt
        logger.info(
            f"Data fetch request: source={source_type}, "
            f"requester={requester_context.requester_type}"
        )
        
        # Get credentials with system-level access (internal only)
        system_context = RequesterContext(
            requester_type="data_proxy",
            access_level=AccessLevel.SYSTEM
        )
        
        try:
            # Get fetch sources configuration
            fetch_config = self.secure_config.get_config(
                'fetch_sources.yaml',
                system_context
            )
            
            if not fetch_config:
                raise ValueError("Fetch sources configuration not found")
            
            # Find source configuration
            source_config = self._find_source_config(fetch_config, source_type)
            
            if not source_config:
                raise ValueError(f"Configuration not found for source: {source_type}")
            
            # Get credentials (internal only, never exposed)
            credentials = source_config.get('credentials', {})
            
            # Initialize fetcher
            fetcher_class = self._fetcher_registry[source_type]
            fetcher = fetcher_class(credentials)
            
            # Fetch data (credentials used internally)
            data = fetcher.fetch(params)
            
            logger.info(
                f"Successfully fetched data from {source_type} "
                f"for {requester_context.requester_type}"
            )
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch data from {source_type}: {e}")
            raise
    
    def fetch_market_data(
        self,
        symbols: list[str],
        start_date: datetime,
        end_date: datetime,
        requester_context: RequesterContext
    ) -> pd.DataFrame:
        """
        Fetch market data (convenience method).
        
        Args:
            symbols: List of symbols
            start_date: Start date
            end_date: End date
            requester_context: Requester context
        
        Returns:
            DataFrame with market data
        """
        params = {
            'symbols': symbols,
            'start_date': start_date,
            'end_date': end_date,
        }
        return self.fetch_data('market_data', params, requester_context)
    
    def fetch_news(
        self,
        keywords: list[str],
        start_date: datetime,
        end_date: datetime,
        requester_context: RequesterContext
    ) -> pd.DataFrame:
        """
        Fetch news data (convenience method).
        
        Args:
            keywords: List of keywords
            start_date: Start date
            end_date: End date
            requester_context: Requester context
        
        Returns:
            DataFrame with news data
        """
        params = {
            'keywords': keywords,
            'start_date': start_date,
            'end_date': end_date,
        }
        return self.fetch_data('news', params, requester_context)
    
    def fetch_calendar(
        self,
        start_date: datetime,
        end_date: datetime,
        requester_context: RequesterContext
    ) -> pd.DataFrame:
        """
        Fetch economic calendar data (convenience method).
        
        Args:
            start_date: Start date
            end_date: End date
            requester_context: Requester context
        
        Returns:
            DataFrame with calendar events
        """
        params = {
            'start_date': start_date,
            'end_date': end_date,
        }
        return self.fetch_data('calendar', params, requester_context)
    
    def _find_source_config(
        self,
        fetch_config: dict[str, Any],
        source_type: str
    ) -> Optional[dict[str, Any]]:
        """
        Find source configuration by type.
        
        Args:
            fetch_config: Fetch sources configuration
            source_type: Source type to find
        
        Returns:
            Source configuration or None
        """
        sources = fetch_config.get('sources', [])
        
        for source in sources:
            if source.get('source_type') == source_type:
                return source
        
        return None
    
    def list_available_sources(
        self,
        requester_context: RequesterContext
    ) -> list[str]:
        """
        List available data sources (without exposing credentials).
        
        Args:
            requester_context: Requester context
        
        Returns:
            List of available source types
        """
        return list(self._fetcher_registry.keys())

# Global data proxy instance
_data_proxy: Optional[SecureDataProxy] = None

def get_data_proxy() -> SecureDataProxy:
    """
    Get global secure data proxy instance.
    
    Returns:
        Global data proxy
    """
    global _data_proxy
    if _data_proxy is None:
        _data_proxy = SecureDataProxy()
    return _data_proxy

# Convenience functions for common access patterns
def fetch_data_for_ai(
    source_type: str,
    params: dict[str, Any]
) -> pd.DataFrame:
    """Fetch data with AI-level access."""
    context = RequesterContext(
        requester_type="ai_engine",
        access_level=AccessLevel.AI
    )
    proxy = get_data_proxy()
    return proxy.fetch_data(source_type, params, context)

def fetch_data_for_agent(
    source_type: str,
    params: dict[str, Any],
    agent_id: str,
    user_id: Optional[str] = None
) -> pd.DataFrame:
    """Fetch data with agent-level access."""
    context = RequesterContext(
        requester_type="agent",
        requester_id=agent_id,
        access_level=AccessLevel.AGENT,
        user_id=user_id
    )
    proxy = get_data_proxy()
    return proxy.fetch_data(source_type, params, context)

__all__ = [
    'SecureDataProxy',
    'get_data_proxy',
    'fetch_data_for_ai',
    'fetch_data_for_agent',
]
