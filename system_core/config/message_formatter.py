"""
Message Formatter

This module provides utilities for formatting push messages with Emoji,
Markdown, and localization support.

All timestamps are automatically converted from UTC to user's configured timezone.
"""

from typing import Any, Optional
from datetime import datetime
import re
from system_core.config.timezone_manager import get_timezone_manager

# Emoji mappings for different categories
EMOJI_MAP = {
    # Countries
    "US": "🇺🇸",
    "EU": "🇪🇺",
    "UK": "🇬🇧",
    "JP": "🇯🇵",
    "CN": "🇨🇳",
    "CA": "🇨🇦",
    "AU": "🇦🇺",
    "CH": "🇨🇭",
    "NZ": "🇳🇿",
    
    # Indicators
    "up": "📈",
    "down": "📉",
    "high": "⬆️",
    "low": "⬇️",
    "neutral": "➡️",
    "warning": "⚠️",
    "alert": "🚨",
    "info": "ℹ️",
    "success": "✅",
    "error": "❌",
    
    # Financial instruments
    "gold": "🥇",
    "silver": "🥈",
    "oil": "🛢️",
    "forex": "💱",
    "stock": "📊",
    "crypto": "₿",
    
    # Currencies
    "USD": "💵",
    "EUR": "💶",
    "GBP": "💷",
    "JPY": "💴",
    "CNY": "💴",
    
    # Actions
    "buy": "🟢",
    "sell": "🔴",
    "hold": "🟡",
    "news": "📰",
    "calendar": "📅",
    "time": "⏰",
    "chart": "📈",
    "report": "📋",
    "robot": "🤖",
    "target": "🎯",
    "explosion": "💥",
    "fire": "🔥",
    "rocket": "🚀",
    "money": "💰",
    "bank": "🏦",
    "briefcase": "💼",
}

class MessageFormatter:
    """
    Formats messages with Emoji, Markdown, and localization.
    
    All timestamps are automatically converted to user's timezone.
    """
    
    def __init__(self, language: str = "zh", timezone: str = "UTC"):
        """
        Initialize message formatter.
        
        Args:
            language: Language code (zh, en)
            timezone: Timezone for timestamp formatting (deprecated, use timezone_manager)
        """
        self.language = language
        self.timezone = timezone  # Kept for backward compatibility
        self.timezone_manager = get_timezone_manager()
    
    def get_emoji(self, key: str) -> str:
        """
        Get emoji for a key.
        
        Args:
            key: Emoji key
        
        Returns:
            Emoji character or empty string if not found
        """
        return EMOJI_MAP.get(key, "")
    
    def format_timestamp(self, dt: Optional[datetime] = None) -> str:
        """
        Format timestamp with user's timezone.
        
        Args:
            dt: Datetime object in UTC (defaults to now)
        
        Returns:
            Formatted timestamp string in user's timezone
        """
        if dt is None:
            dt = self.timezone_manager.now_utc()
        
        return self.timezone_manager.format_datetime(dt)
    
    def format_number(self, value: float, decimals: int = 2) -> str:
        """
        Format number with proper decimal places.
        
        Args:
            value: Number to format
            decimals: Number of decimal places
        
        Returns:
            Formatted number string
        """
        return f"{value:.{decimals}f}"
    
    def format_percentage(self, value: float, decimals: int = 2) -> str:
        """
        Format percentage with sign and emoji.
        
        Args:
            value: Percentage value
            decimals: Number of decimal places
        
        Returns:
            Formatted percentage string with emoji
        """
        emoji = self.get_emoji("up") if value > 0 else self.get_emoji("down") if value < 0 else self.get_emoji("neutral")
        sign = "+" if value > 0 else ""
        return f"{emoji} {sign}{value:.{decimals}f}%"
    
    def format_price(self, symbol: str, price: float, decimals: int = 2) -> str:
        """
        Format price with currency symbol.
        
        Args:
            symbol: Asset symbol
            price: Price value
            decimals: Number of decimal places
        
        Returns:
            Formatted price string
        """
        # Determine currency emoji
        currency_emoji = ""
        if "USD" in symbol:
            currency_emoji = self.get_emoji("USD")
        elif "EUR" in symbol:
            currency_emoji = self.get_emoji("EUR")
        elif "GBP" in symbol:
            currency_emoji = self.get_emoji("GBP")
        elif "JPY" in symbol:
            currency_emoji = self.get_emoji("JPY")
        
        return f"{currency_emoji} {self.format_number(price, decimals)}"
    
    def format_economic_indicator(
        self,
        name: str,
        actual: Optional[float] = None,
        forecast: Optional[float] = None,
        previous: Optional[float] = None,
        country: str = "US"
    ) -> str:
        """
        Format economic indicator data.
        
        Args:
            name: Indicator name
            actual: Actual value
            forecast: Forecast value
            previous: Previous value
            country: Country code
        
        Returns:
            Formatted indicator string
        """
        country_emoji = self.get_emoji(country)
        
        lines = [f"{country_emoji} **{name}**"]
        
        if actual is not None:
            lines.append(f"实际: {self.format_number(actual)}" if self.language == "zh" else f"Actual: {self.format_number(actual)}")
        
        if forecast is not None:
            lines.append(f"预期: {self.format_number(forecast)}" if self.language == "zh" else f"Forecast: {self.format_number(forecast)}")
        
        if previous is not None:
            lines.append(f"前值: {self.format_number(previous)}" if self.language == "zh" else f"Previous: {self.format_number(previous)}")
        
        # Add comparison if actual and previous are available
        if actual is not None and previous is not None:
            diff = actual - previous
            diff_pct = (diff / previous * 100) if previous != 0 else 0
            lines.append(f"变化: {self.format_percentage(diff_pct)}" if self.language == "zh" else f"Change: {self.format_percentage(diff_pct)}")
        
        return "\n".join(lines)
    
    def format_asset_price(
        self,
        symbol: str,
        name_zh: str,
        name_en: str,
        price: float,
        change_pct: Optional[float] = None
    ) -> str:
        """
        Format asset price with name and change.
        
        Args:
            symbol: Asset symbol
            name_zh: Chinese name
            name_en: English name
            price: Current price
            change_pct: Change percentage
        
        Returns:
            Formatted asset price string
        """
        name = name_zh if self.language == "zh" else name_en
        
        # Get appropriate emoji
        emoji = ""
        if "XAU" in symbol or "gold" in name_en.lower():
            emoji = self.get_emoji("gold")
        elif "XAG" in symbol or "silver" in name_en.lower():
            emoji = self.get_emoji("silver")
        elif "OIL" in symbol or "oil" in name_en.lower():
            emoji = self.get_emoji("oil")
        elif any(curr in symbol for curr in ["USD", "EUR", "GBP", "JPY"]):
            emoji = self.get_emoji("forex")
        else:
            emoji = self.get_emoji("chart")
        
        price_str = self.format_price(symbol, price)
        
        if change_pct is not None:
            change_str = self.format_percentage(change_pct)
            return f"{emoji} **{name}**: {price_str} {change_str}"
        else:
            return f"{emoji} **{name}**: {price_str}"
    
    def format_ea_recommendation(
        self,
        ea_name: str,
        win_rate: float,
        loss_rate: float,
        confidence: float
    ) -> str:
        """
        Format EA recommendation.
        
        Args:
            ea_name: EA name
            win_rate: Win rate percentage
            loss_rate: Loss rate percentage
            confidence: Confidence score (0-1)
        
        Returns:
            Formatted EA recommendation string
        """
        robot_emoji = self.get_emoji("robot")
        target_emoji = self.get_emoji("target")
        success_emoji = self.get_emoji("success")
        error_emoji = self.get_emoji("error")
        
        # Format: 🤖Name🎯✅nn% ❌-nn%
        return f"{robot_emoji}{ea_name}{target_emoji}{success_emoji}{win_rate:.0f}% {error_emoji}-{loss_rate:.0f}%"
    
    def compress_news(self, text: str, max_chinese: int = 30, max_english: int = 70) -> str:
        """
        Compress news text to specified length.
        
        Args:
            text: Original text
            max_chinese: Maximum Chinese characters
            max_english: Maximum English characters
        
        Returns:
            Compressed text
        """
        # Count Chinese and English characters
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        # Determine max length based on language
        if chinese_chars > english_chars:
            max_len = max_chinese
        else:
            max_len = max_english
        
        if len(text) <= max_len:
            return text
        
        # Truncate and add ellipsis
        return text[:max_len] + "..."
    
    def format_breaking_news(
        self,
        title: str,
        summary: str,
        source: str,
        timestamp: Optional[datetime] = None,
        priority: str = "high"
    ) -> str:
        """
        Format breaking news message.
        
        Args:
            title: News title
            summary: News summary
            source: News source
            timestamp: Timestamp
            priority: Priority level
        
        Returns:
            Formatted breaking news message
        """
        # Get priority emoji
        if priority == "critical":
            prefix = f"{self.get_emoji('alert')} [紧急]" if self.language == "zh" else f"{self.get_emoji('alert')} [URGENT]"
        elif priority == "high":
            prefix = f"{self.get_emoji('warning')} [重要]" if self.language == "zh" else f"{self.get_emoji('warning')} [IMPORTANT]"
        else:
            prefix = f"{self.get_emoji('info')} [一般]" if self.language == "zh" else f"{self.get_emoji('info')} [INFO]"
        
        news_emoji = self.get_emoji("news")
        calendar_emoji = self.get_emoji("calendar")
        
        # Compress summary
        compressed_summary = self.compress_news(summary)
        
        lines = [
            f"{prefix} **{title}**",
            "",
            f"{calendar_emoji} {self.format_timestamp(timestamp)}",
            f"{news_emoji} {source}",
            "",
            compressed_summary
        ]
        
        return "\n".join(lines)
    
    def format_table(self, headers: list[str], rows: list[list[str]]) -> str:
        """
        Format data as Markdown table.
        
        Args:
            headers: Table headers
            rows: Table rows
        
        Returns:
            Formatted Markdown table
        """
        # Create header row
        header_row = "| " + " | ".join(headers) + " |"
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"
        
        # Create data rows
        data_rows = []
        for row in rows:
            data_rows.append("| " + " | ".join(str(cell) for cell in row) + " |")
        
        return "\n".join([header_row, separator] + data_rows)
    
    def format_daily_report_summary(
        self,
        date: datetime,
        market_summary: str,
        top_assets: list[dict[str, Any]],
        top_news: list[dict[str, Any]]
    ) -> str:
        """
        Format daily report summary.
        
        Args:
            date: Report date
            market_summary: Market summary text
            top_assets: List of top assets with price data
            top_news: List of top news items
        
        Returns:
            Formatted daily report
        """
        report_emoji = self.get_emoji("report")
        chart_emoji = self.get_emoji("chart")
        news_emoji = self.get_emoji("news")
        
        lines = [
            f"{report_emoji} **每日市场报告**" if self.language == "zh" else f"{report_emoji} **Daily Market Report**",
            f"{self.get_emoji('calendar')} {date.strftime('%Y-%m-%d')}",
            "",
            f"## {chart_emoji} 市场概况" if self.language == "zh" else f"## {chart_emoji} Market Overview",
            market_summary,
            ""
        ]
        
        # Add top assets
        if top_assets:
            lines.append(f"## {self.get_emoji('money')} 重点品种" if self.language == "zh" else f"## {self.get_emoji('money')} Top Assets")
            for asset in top_assets:
                lines.append(self.format_asset_price(
                    asset['symbol'],
                    asset['name_zh'],
                    asset['name_en'],
                    asset['price'],
                    asset.get('change_pct')
                ))
            lines.append("")
        
        # Add top news
        if top_news:
            lines.append(f"## {news_emoji} 重要新闻" if self.language == "zh" else f"## {news_emoji} Top News")
            for i, news in enumerate(top_news, 1):
                lines.append(f"{i}. {news['title']}")
            lines.append("")
        
        lines.append(f"---")
        lines.append(f"{self.get_emoji('time')} {self.format_timestamp()}")
        
        return "\n".join(lines)

def get_message_formatter(language: str = "zh", timezone: str = "UTC") -> MessageFormatter:
    """
    Get a MessageFormatter instance.
    
    Args:
        language: Language code (zh, en)
        timezone: Timezone for timestamp formatting
    
    Returns:
        MessageFormatter instance
    """
    return MessageFormatter(language, timezone)
