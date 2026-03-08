"""
Market Data Fetcher

Fetches market price data from Alpha Vantage and similar APIs.

Validates: Requirements 2.1, 2.2, 2.3, 2.7
"""

import aiohttp
from datetime import datetime
from typing import Any

from system_core.config import get_logger
from system_core.fetch_engine.data_fetcher import DataFetcher, RawData
from system_core.fetch_engine.transformer import DataTransformer

logger = get_logger(__name__)

class MarketDataFetcher(DataFetcher):
    """
    Fetcher for market price data (OHLCV).
    
    Supports:
    - Alpha Vantage API
    - Other market data APIs
    """
    
    async def fetch(self) -> dict[str, Any]:
        """
        Fetch market data from API.
        
        Returns:
            Raw API response
            
        Validates: Requirement 2.2
        """
        # Build query parameters
        params = {
            "apikey": self.credentials.get("api_key", ""),
            "function": "FX_INTRADAY",
            "from_symbol": "EUR",
            "to_symbol": "USD",
            "interval": "5min",
            **self.parameters
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.api_endpoint,
                params=params,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                # Log error for 4xx/5xx responses (Requirement 2.5)
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(
                        f"API error for {self.source_id}",
                        extra={
                            "source_id": self.source_id,
                            "status_code": response.status,
                            "request_url": str(response.url),
                            "response_body": error_text
                        }
                    )
                    response.raise_for_status()
                
                return await response.json()
    
    def transform(self, raw_data: dict[str, Any]) -> RawData:
        """
        Transform raw API response to standard format.
        
        Args:
            raw_data: Raw API response
            
        Returns:
            Standardized RawData object
            
        Validates: Requirement 2.3
        """
        # Alpha Vantage response format
        time_series_key = None
        for key in raw_data.keys():
            if "Time Series" in key:
                time_series_key = key
                break
        
        if not time_series_key:
            raise ValueError("No time series data in response")
        
        time_series = raw_data[time_series_key]
        
        # Get most recent data point
        if not time_series:
            raise ValueError("Empty time series")
        
        latest_timestamp = sorted(time_series.keys(), reverse=True)[0]
        latest_data = time_series[latest_timestamp]
        
        # Field mapping for market data
        field_mapping = {
            "open": "1. open",
            "high": "2. high",
            "low": "3. low",
            "close": "4. close",
            "volume": "5. volume"
        }
        
        # Extract and normalize
        extracted = DataTransformer.extract_fields(latest_data, field_mapping)
        extracted["timestamp"] = latest_timestamp
        extracted["symbol"] = raw_data.get("Meta Data", {}).get("2. From Symbol", "UNKNOWN")
        
        normalized = DataTransformer.normalize_types(extracted)
        
        # Validate required fields
        required_fields = ["open", "high", "low", "close", "timestamp"]
        DataTransformer.validate_schema(normalized, required_fields)
        
        # Calculate quality score
        metadata = {"source_api": "market_data", "interval": "5min"}
        quality_score = DataTransformer.calculate_quality_score(normalized, metadata)
        
        # Create RawData object
        timestamp = datetime.fromisoformat(latest_timestamp.replace('Z', '+00:00'))
        
        return RawData(
            source=self.source_id,
            source_type=self.source_type,
            timestamp=timestamp,
            data_type="market_data",
            content=normalized,
            metadata=metadata,
            quality_score=quality_score
        )
