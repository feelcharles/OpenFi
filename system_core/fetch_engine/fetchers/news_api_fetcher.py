"""
News API Fetcher

Fetches news articles from NewsAPI and similar services.

Validates: Requirements 2.1, 2.2, 2.3, 2.7
"""

import aiohttp
from datetime import datetime
from typing import Any

from system_core.config import get_logger
from system_core.fetch_engine.data_fetcher import DataFetcher, RawData
from system_core.fetch_engine.transformer import DataTransformer

logger = get_logger(__name__)

class NewsAPIFetcher(DataFetcher):
    """
    Fetcher for news articles.
    
    Supports:
    - NewsAPI.org
    - Other news APIs
    """
    
    async def fetch(self) -> dict[str, Any]:
        """
        Fetch news articles from API.
        
        Returns:
            Raw API response
            
        Validates: Requirement 2.2
        """
        # Build query parameters
        params = {
            "apiKey": self.credentials.get("api_key", ""),
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
        # NewsAPI response format
        articles = raw_data.get("articles", [])
        
        if not articles:
            raise ValueError("No articles in response")
        
        # Process first article
        article = articles[0]
        
        # Field mapping for news articles
        field_mapping = {
            "title": "title",
            "description": "description",
            "content": "content",
            "source_name": "source.name",
            "author": "author",
            "url": "url",
            "published_at": "publishedAt",
            "id": "url"  # Use URL as unique ID
        }
        
        # Extract and normalize
        extracted = DataTransformer.extract_fields(article, field_mapping)
        normalized = DataTransformer.normalize_types(extracted)
        
        # Validate required fields
        required_fields = ["title", "published_at"]
        DataTransformer.validate_schema(normalized, required_fields)
        
        # Calculate quality score
        metadata = {"source_api": "news_api"}
        quality_score = DataTransformer.calculate_quality_score(normalized, metadata)
        
        # Create RawData object
        timestamp_str = normalized.get("published_at")
        if isinstance(timestamp_str, str):
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            timestamp = datetime.utcnow()
        
        return RawData(
            source=self.source_id,
            source_type=self.source_type,
            timestamp=timestamp,
            data_type="news",
            content=normalized,
            metadata=metadata,
            quality_score=quality_score
        )
