"""
Timezone Manager

This module handles timezone conversions between UTC (internal) and user timezone (display).

Core Principles:
- Internal storage and processing: Always use UTC
- User interface display: Convert to user's configured timezone
- Scheduled tasks: User's time is converted to UTC for execution
"""

from datetime import datetime, timezone as dt_timezone
from typing import Optional
from zoneinfo import ZoneInfo
import yaml
from pathlib import Path

class TimezoneManager:
    """
    Manages timezone conversions between UTC and user timezone.
    
    All internal times are stored in UTC. User-facing times are converted
    to the user's configured timezone.
    """
    
    def __init__(
        self,
        user_timezone: str = "UTC",
        datetime_format: str = "%Y-%m-%d %H:%M:%S",
        date_format: str = "%Y-%m-%d",
        time_format: str = "%H:%M:%S",
        show_timezone_name: bool = True,
        use_12_hour_format: bool = False
    ):
        """
        Initialize timezone manager.
        
        Args:
            user_timezone: IANA timezone name (e.g., "Asia/Shanghai")
            datetime_format: Format string for datetime display
            date_format: Format string for date display
            time_format: Format string for time display
            show_timezone_name: Whether to show timezone abbreviation
            use_12_hour_format: Whether to use 12-hour format
        """
        self.user_timezone = ZoneInfo(user_timezone)
        self.user_timezone_name = user_timezone
        self.datetime_format = datetime_format
        self.date_format = date_format
        self.time_format = time_format
        self.show_timezone_name = show_timezone_name
        self.use_12_hour_format = use_12_hour_format
        
        # Adjust format for 12-hour format
        if use_12_hour_format:
            self.datetime_format = self.datetime_format.replace("%H", "%I").replace("%M", "%M %p")
            self.time_format = self.time_format.replace("%H", "%I").replace("%M", "%M %p")
    
    @classmethod
    def from_config(cls, config_path: str = "config/push_config.yaml") -> "TimezoneManager":
        """
        Create TimezoneManager from configuration file.
        
        Args:
            config_path: Path to push configuration file
        
        Returns:
            TimezoneManager instance
        """
        config_file = Path(config_path)
        if not config_file.exists():
            # Return default UTC timezone manager
            return cls()
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        tz_config = config.get('user_timezone', {})
        
        return cls(
            user_timezone=tz_config.get('timezone', 'UTC'),
            datetime_format=tz_config.get('datetime_format', '%Y-%m-%d %H:%M:%S'),
            date_format=tz_config.get('date_format', '%Y-%m-%d'),
            time_format=tz_config.get('time_format', '%H:%M:%S'),
            show_timezone_name=tz_config.get('show_timezone_name', True),
            use_12_hour_format=tz_config.get('use_12_hour_format', False)
        )
    
    @classmethod
    def from_user(cls, user) -> "TimezoneManager":
        """
        Create TimezoneManager from user object (for future multi-user support).
        
        Args:
            user: User object with timezone settings
        
        Returns:
            TimezoneManager instance
        
        Note:
            This method is reserved for future multi-user functionality.
            Currently, the system uses a single global timezone configuration.
        """
        return cls(
            user_timezone=getattr(user, 'timezone', 'UTC'),
            datetime_format=getattr(user, 'datetime_format', '%Y-%m-%d %H:%M:%S'),
            date_format=getattr(user, 'date_format', '%Y-%m-%d'),
            time_format=getattr(user, 'time_format', '%H:%M:%S'),
            show_timezone_name=getattr(user, 'show_timezone_name', True),
            use_12_hour_format=getattr(user, 'use_12_hour_format', False)
        )
    
    def utc_to_user(self, utc_dt: datetime) -> datetime:
        """
        Convert UTC datetime to user timezone.
        
        Args:
            utc_dt: Datetime in UTC (can be naive or aware)
        
        Returns:
            Datetime in user timezone (aware)
        """
        # Ensure datetime is UTC aware
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=dt_timezone.utc)
        elif utc_dt.tzinfo != dt_timezone.utc:
            # Convert to UTC first
            utc_dt = utc_dt.astimezone(dt_timezone.utc)
        
        # Convert to user timezone
        return utc_dt.astimezone(self.user_timezone)
    
    def user_to_utc(self, user_dt: datetime) -> datetime:
        """
        Convert user timezone datetime to UTC.
        
        Args:
            user_dt: Datetime in user timezone (can be naive or aware)
        
        Returns:
            Datetime in UTC (aware)
        """
        # If naive, assume it's in user timezone
        if user_dt.tzinfo is None:
            user_dt = user_dt.replace(tzinfo=self.user_timezone)
        
        # Convert to UTC
        return user_dt.astimezone(dt_timezone.utc)
    
    def now_utc(self) -> datetime:
        """
        Get current time in UTC.
        
        Returns:
            Current datetime in UTC (aware)
        """
        return datetime.now(dt_timezone.utc)
    
    def now_user(self) -> datetime:
        """
        Get current time in user timezone.
        
        Returns:
            Current datetime in user timezone (aware)
        """
        return datetime.now(self.user_timezone)
    
    def format_datetime(self, dt: datetime, in_user_timezone: bool = True) -> str:
        """
        Format datetime for display to user.
        
        Args:
            dt: Datetime to format (can be in any timezone)
            in_user_timezone: Whether to convert to user timezone first
        
        Returns:
            Formatted datetime string
        """
        if in_user_timezone:
            dt = self.utc_to_user(dt)
        
        formatted = dt.strftime(self.datetime_format)
        
        if self.show_timezone_name:
            # Get timezone abbreviation
            tz_name = dt.tzname()
            formatted = f"{formatted} {tz_name}"
        
        return formatted
    
    def format_date(self, dt: datetime, in_user_timezone: bool = True) -> str:
        """
        Format date for display to user.
        
        Args:
            dt: Datetime to format
            in_user_timezone: Whether to convert to user timezone first
        
        Returns:
            Formatted date string
        """
        if in_user_timezone:
            dt = self.utc_to_user(dt)
        
        return dt.strftime(self.date_format)
    
    def format_time(self, dt: datetime, in_user_timezone: bool = True) -> str:
        """
        Format time for display to user.
        
        Args:
            dt: Datetime to format
            in_user_timezone: Whether to convert to user timezone first
        
        Returns:
            Formatted time string
        """
        if in_user_timezone:
            dt = self.utc_to_user(dt)
        
        return dt.strftime(self.time_format)
    
    def parse_user_time(self, time_str: str, date: Optional[datetime] = None) -> datetime:
        """
        Parse time string in user timezone and convert to UTC.
        
        Args:
            time_str: Time string (e.g., "16:00", "16:00:00")
            date: Optional date to use (defaults to today in user timezone)
        
        Returns:
            Datetime in UTC
        """
        if date is None:
            date = self.now_user()
        
        # Parse time
        if ":" in time_str:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            second = int(parts[2]) if len(parts) > 2 else 0
        else:
            raise ValueError(f"Invalid time format: {time_str}")
        
        # Create datetime in user timezone
        user_dt = date.replace(hour=hour, minute=minute, second=second, microsecond=0)
        
        # Convert to UTC
        return self.user_to_utc(user_dt)
    
    def get_timezone_offset(self) -> str:
        """
        Get timezone offset string (e.g., "+08:00", "-05:00").
        
        Returns:
            Timezone offset string
        """
        now = self.now_user()
        offset = now.strftime("%z")
        # Format as +HH:MM
        return f"{offset[:3]}:{offset[3:]}"
    
    def get_default_timezone(self) -> str:
        """
        Get the default timezone name.
        
        Returns:
            IANA timezone name (e.g., "Asia/Shanghai", "UTC")
        """
        return self.user_timezone_name
    
    def get_supported_timezones(self) -> list[str]:
        """
        Get list of supported timezone names.
        
        Returns:
            List of IANA timezone names
        """
        # Return common timezones - in production this could be more comprehensive
        return [
            "UTC",
            "Asia/Shanghai",
            "Asia/Hong_Kong",
            "Asia/Tokyo",
            "Europe/London",
            "Europe/Paris",
            "America/New_York",
            "America/Chicago",
            "America/Los_Angeles",
        ]
    
    def get_timezone_info(self) -> dict:
        """
        Get timezone information.
        
        Returns:
            Dictionary with timezone information
        """
        now = self.now_user()
        return {
            "timezone": self.user_timezone_name,
            "offset": self.get_timezone_offset(),
            "abbreviation": now.tzname(),
            "current_time": self.format_datetime(now, in_user_timezone=False),
            "utc_time": self.format_datetime(self.now_utc(), in_user_timezone=False),
        }

    def get_default_timezone(self) -> str:
        """
        Get the default timezone name.

        Returns:
            IANA timezone name (e.g., "Asia/Shanghai", "UTC")
        """
        return self.user_timezone_name

# Global instance
_timezone_manager: Optional[TimezoneManager] = None

def get_timezone_manager(config_path: str = "config/push_config.yaml") -> TimezoneManager:
    """
    Get or create the global TimezoneManager instance.
    
    Args:
        config_path: Path to push configuration file
    
    Returns:
        TimezoneManager instance
    """
    global _timezone_manager
    if _timezone_manager is None:
        _timezone_manager = TimezoneManager.from_config(config_path)
    return _timezone_manager

def reset_timezone_manager():
    """Reset the global timezone manager (useful for testing)."""
    global _timezone_manager
    _timezone_manager = None
