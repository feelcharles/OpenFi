"""
Economic Calendar Fetcher

Fetches economic calendar events from ForexFactory and similar APIs.

Validates: Requirements 2.1, 2.2, 2.3, 2.7
"""

import aiohttp
from datetime import datetime
from typing import Any

from system_core.config import get_logger
from system_core.fetch_engine.data_fetcher import DataFetcher, RawData
from system_core.fetch_engine.transformer import DataTransformer

logger = get_logger(__name__)

class EconomicCalendarFetcher(DataFetcher):
    """
    Fetcher for economic calendar events.
    
    Supports:
    - ForexFactory API
    - Other economic calendar APIs
    """
    
    async def fetch(self) -> dict[str, Any]:
        """
        Fetch economic calendar data from API.
        
        Returns:
            Raw API response
            
        Validates: Requirement 2.2
        """
        headers = {}
        
        # Add API key if present
        if "api_key" in self.credentials:
            headers["Authorization"] = f"Bearer {self.credentials['api_key']}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.api_endpoint,
                headers=headers,
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
        # Handle different API response formats
        events = raw_data.get("events", raw_data.get("data", []))
        
        if not isinstance(events, list):
            events = [raw_data]
        
        # Process first event (or could process all in batch)
        if not events:
            raise ValueError("No events in response")
        
        event = events[0]
        
        # Field mapping for economic calendar
        field_mapping = {
            "event_name": "title",
            "country": "country",
            "currency": "currency",
            "impact": "impact",
            "forecast": "forecast",
            "previous": "previous",
            "actual": "actual",
            "timestamp": "date",
            "id": "id"
        }
        
        # Extract and normalize
        extracted = DataTransformer.extract_fields(event, field_mapping)
        normalized = DataTransformer.normalize_types(extracted)
        
        # Validate required fields
        required_fields = ["event_name", "country", "timestamp"]
        DataTransformer.validate_schema(normalized, required_fields)
        
        # Calculate quality score
        metadata = {"source_api": "economic_calendar"}
        quality_score = DataTransformer.calculate_quality_score(normalized, metadata)
        
        # Create RawData object
        timestamp = normalized.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.utcnow()
        
        return RawData(
            source=self.source_id,
            source_type=self.source_type,
            timestamp=timestamp,
            data_type="economic_event",
            content=normalized,
            metadata=metadata,
            quality_score=quality_score
        )
