"""
Social Media Fetcher

Fetches posts from Twitter/X and other social media platforms.

Validates: Requirements 2.1, 2.2, 2.3, 2.7
"""

import aiohttp
from datetime import datetime
from typing import Any

from system_core.config import get_logger
from system_core.fetch_engine.data_fetcher import DataFetcher, RawData
from system_core.fetch_engine.transformer import DataTransformer

logger = get_logger(__name__)

class SocialMediaFetcher(DataFetcher):
    """
    Fetcher for social media posts.
    
    Supports:
    - Twitter/X API v2
    - Other social media APIs
    """
    
    async def fetch(self) -> dict[str, Any]:
        """
        Fetch social media posts from API.
        
        Returns:
            Raw API response
            
        Validates: Requirement 2.2
        """
        # Build headers with authentication
        headers = {}
        
        if "api_key" in self.credentials:
            headers["Authorization"] = f"Bearer {self.credentials['api_key']}"
        
        # Build query parameters
        params = self.parameters.copy()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.api_endpoint,
                headers=headers,
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
        # Twitter API v2 response format
        tweets = raw_data.get("data", [])
        
        if not tweets:
            raise ValueError("No tweets in response")
        
        # Process first tweet
        tweet = tweets[0]
        
        # Field mapping for social media posts
        field_mapping = {
            "text": "text",
            "author_id": "author_id",
            "created_at": "created_at",
            "id": "id",
            "retweet_count": "public_metrics.retweet_count",
            "reply_count": "public_metrics.reply_count",
            "like_count": "public_metrics.like_count",
            "quote_count": "public_metrics.quote_count"
        }
        
        # Extract and normalize
        extracted = DataTransformer.extract_fields(tweet, field_mapping)
        normalized = DataTransformer.normalize_types(extracted)
        
        # Calculate engagement score
        engagement = (
            normalized.get("retweet_count", 0) +
            normalized.get("reply_count", 0) +
            normalized.get("like_count", 0) +
            normalized.get("quote_count", 0)
        )
        normalized["engagement_score"] = engagement
        
        # Validate required fields
        required_fields = ["text", "created_at", "id"]
        DataTransformer.validate_schema(normalized, required_fields)
        
        # Calculate quality score
        metadata = {"source_api": "social_media", "platform": "twitter"}
        quality_score = DataTransformer.calculate_quality_score(normalized, metadata)
        
        # Create RawData object
        timestamp_str = normalized.get("created_at")
        if isinstance(timestamp_str, str):
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            timestamp = datetime.utcnow()
        
        return RawData(
            source=self.source_id,
            source_type=self.source_type,
            timestamp=timestamp,
            data_type="social_post",
            content=normalized,
            metadata=metadata,
            quality_score=quality_score
        )
