"""
Alert configuration loader and manager.

Validates: Requirements 36.5, 36.6
"""

import os
from typing import Optional, Any
from pathlib import Path
import yaml
from pydantic import BaseModel, Field

from .logger import get_logger

logger = get_logger(__name__)

class PagerDutyConfig(BaseModel):
    """PagerDuty configuration."""
    enabled: bool = False
    integration_key: Optional[str] = None
    webhook_url: Optional[str] = None

class OpsgenieConfig(BaseModel):
    """Opsgenie configuration."""
    enabled: bool = False
    api_key: Optional[str] = None
    webhook_url: Optional[str] = None

class SlackConfig(BaseModel):
    """Slack configuration."""
    enabled: bool = False
    webhook_url: Optional[str] = None

class ThresholdsConfig(BaseModel):
    """Alert thresholds configuration."""
    error_rate: float = 0.05
    success_rate: float = 0.90
    latency_seconds: float = 5.0
    queue_depth_warning: int = 8000
    queue_depth_critical: int = 9500
    queue_depth_max: int = 10000

class NotificationRetryConfig(BaseModel):
    """Notification retry configuration."""
    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    max_delay_seconds: float = 30.0

class NotificationConfig(BaseModel):
    """Notification format configuration."""
    include_fields: list[str] = Field(
        default_factory=lambda: [
            "severity",
            "component",
            "condition",
            "message",
            "timestamp",
            "metadata",
            "runbook_url"
        ]
    )
    timezone: str = "UTC"
    retry: NotificationRetryConfig = Field(default_factory=NotificationRetryConfig)

class AlertingConfig(BaseModel):
    """Main alerting configuration."""
    enabled: bool = True
    deduplication_window_seconds: int = 300
    pagerduty: PagerDutyConfig = Field(default_factory=PagerDutyConfig)
    opsgenie: OpsgenieConfig = Field(default_factory=OpsgenieConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    runbooks: dict[str, str] = Field(default_factory=dict)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    notification: NotificationConfig = Field(default_factory=NotificationConfig)

class ComponentConfig(BaseModel):
    """Component-specific alert configuration."""
    enabled: bool = True
    min_severity: str = "warning"

class AlertConfig(BaseModel):
    """Complete alert configuration."""
    alerting: AlertingConfig
    routing: list[dict[str, Any]] = Field(default_factory=list)
    components: dict[str, ComponentConfig] = Field(default_factory=dict)

def load_alert_config(config_path: Optional[Path] = None) -> AlertConfig:
    """
    Load alert configuration from YAML file.
    
    Args:
        config_path: Path to configuration file (default: config/alerting_config.yaml)
        
    Returns:
        AlertConfig: Loaded configuration
        
    Raises:
        FileNotFoundError: If configuration file not found
        ValueError: If configuration is invalid
    """
    if config_path is None:
        config_path = Path("config/alerting_config.yaml")
    
    if not config_path.exists():
        logger.warning(
            "alert_config_not_found",
            path=str(config_path),
            message="Using default configuration"
        )
        return AlertConfig(
            alerting=AlertingConfig(),
            routing=[],
            components={}
        )
    
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Expand environment variables
        config_data = _expand_env_vars(config_data)
        
        config = AlertConfig(**config_data)
        
        logger.info(
            "alert_config_loaded",
            path=str(config_path),
            enabled=config.alerting.enabled,
            pagerduty_enabled=config.alerting.pagerduty.enabled,
            opsgenie_enabled=config.alerting.opsgenie.enabled,
            slack_enabled=config.alerting.slack.enabled
        )
        
        return config
        
    except Exception as e:
        logger.error(
            "alert_config_load_failed",
            path=str(config_path),
            error=str(e)
        )
        raise ValueError(f"Failed to load alert configuration: {e}")

def _expand_env_vars(data: Any) -> Any:
    """
    Recursively expand environment variables in configuration.
    
    Supports ${VAR_NAME} syntax.
    """
    if isinstance(data, dict):
        return {k: _expand_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_expand_env_vars(item) for item in data]
    elif isinstance(data, str):
        # Expand ${VAR_NAME} syntax
        if data.startswith("${") and data.endswith("}"):
            var_name = data[2:-1]
            return os.environ.get(var_name, "")
        return data
    else:
        return data

def get_runbook_url(condition: str, config: Optional[AlertConfig] = None) -> Optional[str]:
    """
    Get runbook URL for a specific alert condition.
    
    Args:
        condition: Alert condition name
        config: Alert configuration (loads default if None)
        
    Returns:
        str: Runbook URL or None if not found
    """
    if config is None:
        config = load_alert_config()
    
    return config.alerting.runbooks.get(condition)

def should_send_alert(
    component: str,
    severity: str,
    config: Optional[AlertConfig] = None
) -> bool:
    """
    Check if alert should be sent based on component and severity settings.
    
    Args:
        component: Component name
        severity: Alert severity
        config: Alert configuration (loads default if None)
        
    Returns:
        bool: True if alert should be sent
    """
    if config is None:
        config = load_alert_config()
    
    # Check if alerting is globally enabled
    if not config.alerting.enabled:
        return False
    
    # Check component-specific settings
    if component in config.components:
        comp_config = config.components[component]
        if not comp_config.enabled:
            return False
        
        # Check minimum severity
        severity_order = ["info", "warning", "error", "critical"]
        min_severity_idx = severity_order.index(comp_config.min_severity)
        current_severity_idx = severity_order.index(severity)
        
        if current_severity_idx < min_severity_idx:
            return False
    
    return True

def get_channels_for_alert(
    severity: str,
    config: Optional[AlertConfig] = None
) -> list[str]:
    """
    Get notification channels for an alert based on severity.
    
    Args:
        severity: Alert severity
        config: Alert configuration (loads default if None)
        
    Returns:
        list[str]: List of channel names
    """
    if config is None:
        config = load_alert_config()
    
    # Find matching routing rule
    for rule in config.routing:
        if rule.get("severity") == severity:
            return rule.get("channels", [])
    
    # Default: send to all enabled channels
    channels = []
    if config.alerting.pagerduty.enabled:
        channels.append("pagerduty")
    if config.alerting.opsgenie.enabled:
        channels.append("opsgenie")
    if config.alerting.slack.enabled:
        channels.append("slack")
    
    return channels
