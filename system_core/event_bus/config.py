"""
Event Bus Configuration Loader

Loads and validates Event Bus configuration from YAML file.
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

from system_core.core.exceptions import ConfigurationError

class RedisConfig(BaseModel):
    """Redis connection configuration."""
    
    url: str = Field(description="Redis connection URL")
    password: Optional[str] = Field(default=None, description="Redis password")
    pool_min_size: int = Field(default=5, ge=1, description="Minimum pool size")
    pool_max_size: int = Field(default=20, ge=1, description="Maximum pool size")
    connection_timeout: int = Field(default=30, ge=1, description="Connection timeout (seconds)")
    socket_timeout: int = Field(default=30, ge=1, description="Socket timeout (seconds)")
    socket_keepalive: bool = Field(default=True, description="Enable socket keepalive")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    health_check_interval: int = Field(default=30, ge=1, description="Health check interval (seconds)")

class TopicConfig(BaseModel):
    """Topic configuration."""
    
    name: str = Field(description="Topic name")
    description: str = Field(default="", description="Topic description")
    retention_seconds: int = Field(default=3600, ge=0, description="Message retention (seconds)")
    max_queue_depth: int = Field(default=10000, ge=1, description="Maximum queue depth")

class DeadLetterQueueConfig(BaseModel):
    """Dead Letter Queue configuration."""
    
    enabled: bool = Field(default=True, description="Enable DLQ")
    max_retry_attempts: int = Field(default=3, ge=1, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(default=60, ge=1, description="Retry delay (seconds)")
    retry_backoff_multiplier: int = Field(default=2, ge=1, description="Backoff multiplier")
    retention_days: int = Field(default=7, ge=1, description="Retention period (days)")
    max_size: int = Field(default=10000, ge=1, description="Maximum DLQ size")

class MetricsConfig(BaseModel):
    """Metrics configuration."""
    
    enabled: bool = Field(default=True, description="Enable metrics")
    export_interval_seconds: int = Field(default=15, ge=1, description="Export interval (seconds)")
    include_per_topic_metrics: bool = Field(default=True, description="Include per-topic metrics")
    include_subscriber_metrics: bool = Field(default=True, description="Include subscriber metrics")
    prometheus_port: int = Field(default=8001, ge=1024, le=65535, description="Prometheus port")

class ShutdownConfig(BaseModel):
    """Graceful shutdown configuration."""
    
    grace_period_seconds: int = Field(default=30, ge=1, description="Grace period (seconds)")
    wait_for_in_flight: bool = Field(default=True, description="Wait for in-flight messages")
    drain_queues: bool = Field(default=False, description="Drain queues on shutdown")

class EventBusConfig(BaseModel):
    """Complete Event Bus configuration."""
    
    redis: RedisConfig
    topics: list[TopicConfig] = Field(default_factory=list)
    dead_letter_queue: DeadLetterQueueConfig = Field(default_factory=DeadLetterQueueConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    shutdown: ShutdownConfig = Field(default_factory=ShutdownConfig)

def load_event_bus_config(config_path: Optional[str] = None) -> EventBusConfig:
    """
    Load Event Bus configuration from YAML file.
    
    Args:
        config_path: Path to config file (default: config/event_bus.yaml)
        
    Returns:
        EventBusConfig object
        
    Raises:
        ConfigurationError: If config file is invalid or missing
    """
    if config_path is None:
        config_path = "config/event_bus.yaml"
    
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise ConfigurationError(f"Event Bus config file not found: {config_path}")
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # Expand environment variables
        config_data = _expand_env_vars(config_data)
        
        # Validate and create config object
        return EventBusConfig(**config_data)
    
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in Event Bus config: {e}")
    
    except Exception as e:
        raise ConfigurationError(f"Failed to load Event Bus config: {e}")

def _expand_env_vars(data: Any) -> Any:
    """
    Recursively expand environment variables in config data.
    
    Replaces ${VAR_NAME} with environment variable value.
    
    Args:
        data: Config data (dict, list, or primitive)
        
    Returns:
        Data with expanded environment variables
    """
    if isinstance(data, dict):
        return {key: _expand_env_vars(value) for key, value in data.items()}
    
    elif isinstance(data, list):
        return [_expand_env_vars(item) for item in data]
    
    elif isinstance(data, str):
        # Replace ${VAR_NAME} with environment variable
        if data.startswith('${') and data.endswith('}'):
            var_name = data[2:-1]
            return os.getenv(var_name, data)
        return data
    
    else:
        return data
