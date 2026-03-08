"""
Data Fetcher Implementations

Specific fetcher implementations for different data sources.
"""

from .economic_calendar_fetcher import EconomicCalendarFetcher
from .market_data_fetcher import MarketDataFetcher
from .news_api_fetcher import NewsAPIFetcher
from .social_media_fetcher import SocialMediaFetcher

__all__ = [
    "EconomicCalendarFetcher",
    "MarketDataFetcher",
    "NewsAPIFetcher",
    "SocialMediaFetcher"
]
