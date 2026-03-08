"""
Fetch Engine Module

Data acquisition engine for fetching information from multiple external sources.
"""

from .fetch_engine import FetchEngine
from .data_fetcher import DataFetcher, RawData
from .transformer import DataTransformer
from .fetchers import (
    EconomicCalendarFetcher,
    MarketDataFetcher,
    NewsAPIFetcher,
    SocialMediaFetcher
)

__all__ = [
    "FetchEngine",
    "DataFetcher",
    "RawData",
    "DataTransformer",
    "EconomicCalendarFetcher",
    "MarketDataFetcher",
    "NewsAPIFetcher",
    "SocialMediaFetcher"
]
