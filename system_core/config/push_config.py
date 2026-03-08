"""
Push Configuration Management

This module handles loading and managing push service configurations
including channels, strategies, templates, and message formatting.
"""

from pathlib import Path
from typing import Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime
import yaml

class ChannelConfig(BaseModel):
    """Push channel configuration"""
    enabled: bool = True
    timeout: int = 10
    # Channel-specific fields stored as dict for flexibility
    config: dict[str, Any] = Field(default_factory=dict)

class MessageFormat(BaseModel):
    """Message format configuration"""
    title_prefix: str = ""
    include_timestamp: bool = True
    include_source: bool = True
    include_summary: bool = True
    include_full_content: bool = False
    include_ai_analysis: bool = True
    include_trading_suggestions: bool = False

class RetryConfig(BaseModel):
    """Retry strategy configuration"""
    enabled: bool = True
    max_attempts: int = 2
    backoff_seconds: int = 5

class PushStrategy(BaseModel):
    """Push strategy configuration"""
    immediate: bool = True
    channels: list[str] = Field(default_factory=list)
    include_current_price: bool = True
    trigger_ea_backtest: bool = False
    message_format: MessageFormat = Field(default_factory=MessageFormat)
    retry: RetryConfig = Field(default_factory=RetryConfig)

class EconomicDataPushConfig(BaseModel):
    """Economic data push configuration"""
    enabled: bool = True
    before_release_minutes: int = 15
    after_release_minutes: int = 5
    content: dict[str, bool] = Field(default_factory=dict)
    important_indicators: list[str] = Field(default_factory=list)

class ScheduleConfig(BaseModel):
    """Schedule configuration for reports"""
    type: str  # every_n_hours, every_n_days, every_n_weeks, every_n_minutes
    value: int
    time_utc: Optional[str] = None
    day_of_week: Optional[str] = None

class ReportContent(BaseModel):
    """Report content configuration"""
    include_market_summary: bool = True
    include_top_news: bool = True
    include_ai_insights: bool = True
    include_trading_opportunities: bool = True
    include_performance_stats: bool = True
    include_charts: bool = False
    max_news_items: int = 10

class ScheduledReport(BaseModel):
    """Scheduled report configuration"""
    enabled: bool = True
    schedule: ScheduleConfig
    channels: list[str] = Field(default_factory=list)
    content: ReportContent = Field(default_factory=ReportContent)
    format: str = "markdown"  # markdown, html

class EABacktestConfig(BaseModel):
    """EA backtest configuration"""
    enabled: bool = True
    backtest_hours: int = 24
    simulation_lot_size: float = 0.01
    max_ea_count: int = 5
    timeout_seconds: int = 30
    result_format: dict[str, bool] = Field(default_factory=dict)
    min_confidence_threshold: float = 0.7

class QuietHours(BaseModel):
    """Quiet hours configuration"""
    enabled: bool = False
    start_time_utc: str = "22:00"
    end_time_utc: str = "06:00"
    allowed_priorities: list[str] = Field(default_factory=list)

class Deduplication(BaseModel):
    """Message deduplication configuration"""
    enabled: bool = True
    time_window_minutes: int = 60
    similarity_threshold: float = 0.9

class PushLimits(BaseModel):
    """Push limits and control"""
    max_pushes_per_hour: int = 50
    max_pushes_per_day: int = 500
    quiet_hours: QuietHours = Field(default_factory=QuietHours)
    deduplication: Deduplication = Field(default_factory=Deduplication)

class Monitoring(BaseModel):
    """Push monitoring configuration"""
    log_all_pushes: bool = True
    alert_on_failure: bool = True
    track_success_rate: bool = True
    track_latency: bool = True
    generate_stats_report: bool = True
    stats_report_interval_hours: int = 24

class PushConfig(BaseModel):
    """Complete push configuration"""
    channels: dict[str, ChannelConfig] = Field(default_factory=dict)
    push_strategies: dict[str, PushStrategy] = Field(default_factory=dict)
    economic_data_push: EconomicDataPushConfig = Field(default_factory=EconomicDataPushConfig)
    scheduled_reports: dict[str, ScheduledReport] = Field(default_factory=dict)
    ea_backtest: EABacktestConfig = Field(default_factory=EABacktestConfig)
    message_templates: dict[str, dict[str, str]] = Field(default_factory=dict)
    push_limits: PushLimits = Field(default_factory=PushLimits)
    monitoring: Monitoring = Field(default_factory=Monitoring)

class PushConfigManager:
    """
    Manages push service configuration.
    
    Loads from config/push_config.yaml
    """
    
    def __init__(self, config_path: str = "config/push_config.yaml"):
        self.config_path = Path(config_path)
        self.config: Optional[PushConfig] = None
    
    def load(self) -> PushConfig:
        """Load push configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Push config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self.config = PushConfig(**data)
        return self.config
    
    def get_channel_config(self, channel_name: str) -> Optional[ChannelConfig]:
        """Get configuration for a specific channel"""
        if self.config is None:
            self.load()
        
        return self.config.channels.get(channel_name)
    
    def get_enabled_channels(self) -> list[str]:
        """Get list of enabled channel names"""
        if self.config is None:
            self.load()
        
        return [name for name, config in self.config.channels.items() if config.enabled]
    
    def is_channel_enabled(self, channel_name: str) -> bool:
        """
        Check if a specific channel is enabled.
        
        Args:
            channel_name: Name of the channel to check
        
        Returns:
            True if channel exists and is enabled, False otherwise
        """
        if self.config is None:
            self.load()
        
        channel_config = self.config.channels.get(channel_name)
        return channel_config.enabled if channel_config else False

    def is_channel_enabled(self, channel_name: str) -> bool:
        """
        Check if a specific channel is enabled.

        Args:
            channel_name: Name of the channel to check

        Returns:
            True if channel exists and is enabled, False otherwise
        """
        if self.config is None:
            self.load()

        channel_config = self.config.channels.get(channel_name)
        return channel_config.enabled if channel_config else False
    
    def get_push_strategy(self, priority: str) -> Optional[PushStrategy]:
        """Get push strategy for a priority level"""
        if self.config is None:
            self.load()
        
        return self.config.push_strategies.get(priority)
    
    def should_push_immediately(self, priority: str) -> bool:
        """Check if a priority level should trigger immediate push"""
        strategy = self.get_push_strategy(priority)
        return strategy.immediate if strategy else False
    
    def get_message_template(self, template_type: str, channel: str = "telegram") -> Optional[str]:
        """Get message template for a specific type and channel"""
        if self.config is None:
            self.load()
        
        templates = self.config.message_templates.get(template_type, {})
        return templates.get(channel)
    
    def format_message(
        self,
        template_type: str,
        channel: str,
        data: dict[str, Any],
        timezone: str = "UTC"
    ) -> str:
        """
        Format a message using template and data.
        
        Args:
            template_type: Type of template (breaking_news, economic_data, daily_report)
            channel: Channel name (telegram, discord, email_html)
            data: Data to fill template
            timezone: Timezone for timestamp formatting
        
        Returns:
            Formatted message string
        """
        template = self.get_message_template(template_type, channel)
        if not template:
            return ""
        
        # Add timestamp if not provided
        if 'timestamp' not in data and 'release_time' not in data:
            data['timestamp'] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Format the template
        try:
            return template.format(**data)
        except KeyError as e:
            # Missing key in data, return template with available data
            return template.format_map(data)
    
    def is_in_quiet_hours(self, current_time: datetime) -> bool:
        """Check if current time is in quiet hours"""
        if self.config is None:
            self.load()
        
        if not self.config.push_limits.quiet_hours.enabled:
            return False
        
        # Parse quiet hours
        start_time = self.config.push_limits.quiet_hours.start_time_utc
        end_time = self.config.push_limits.quiet_hours.end_time_utc
        
        # Simple time comparison (assumes UTC)
        current_hour_min = current_time.strftime("%H:%M")
        
        # Handle overnight quiet hours (e.g., 22:00 to 06:00)
        if start_time > end_time:
            return current_hour_min >= start_time or current_hour_min <= end_time
        else:
            return start_time <= current_hour_min <= end_time
    
    def can_push_in_quiet_hours(self, priority: str) -> bool:
        """Check if a priority level can push during quiet hours"""
        if self.config is None:
            self.load()
        
        return priority in self.config.push_limits.quiet_hours.allowed_priorities
    
    def get_scheduled_reports(self) -> dict[str, ScheduledReport]:
        """Get all scheduled reports"""
        if self.config is None:
            self.load()
        
        return self.config.scheduled_reports
    
    def get_ea_backtest_config(self) -> EABacktestConfig:
        """Get EA backtest configuration"""
        if self.config is None:
            self.load()
        
        return self.config.ea_backtest

# Global instance
_push_config_manager: Optional[PushConfigManager] = None

def get_push_config_manager(config_path: str = "config/push_config.yaml") -> PushConfigManager:
    """
    Get or create the global PushConfigManager instance.
    
    Args:
        config_path: Path to push configuration file
    
    Returns:
        PushConfigManager instance
    """
    global _push_config_manager
    if _push_config_manager is None:
        _push_config_manager = PushConfigManager(config_path)
    return _push_config_manager
