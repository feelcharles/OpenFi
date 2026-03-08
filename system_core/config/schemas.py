"""
Pydantic models for configuration validation.

Provides type-safe validation for all configuration files.

Validates: Requirements 31.2, 31.5, 31.6
"""

from decimal import Decimal
from enum import Enum
from typing import Any, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Type
else:
    Type = type

from pydantic import BaseModel, Field, field_validator, model_validator

# ============================================================================
# Fetch Sources Configuration
# ============================================================================

class ScheduleType(str, Enum):
    """Schedule type enumeration."""
    CRON = "cron"
    INTERVAL = "interval"

class FetchSourceConfig(BaseModel):
    """Configuration for a single fetch source."""
    source_id: str = Field(..., description="Unique identifier for the source")
    source_type: str = Field(..., description="Type of data source")
    api_endpoint: str = Field(..., description="API endpoint URL")
    credentials: dict[str, Any] = Field(default_factory=dict, description="API credentials")
    schedule_type: ScheduleType = Field(..., description="Scheduling type")
    schedule_config: dict[str, Any] = Field(..., description="Schedule configuration")
    enabled: bool = Field(default=True, description="Whether source is enabled")
    retry_count: int = Field(default=3, ge=0, le=10, description="Number of retry attempts")
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Source-specific parameters")

class FetchSourcesConfig(BaseModel):
    """Configuration for all fetch sources."""
    sources: list[FetchSourceConfig] = Field(..., description="List of fetch sources")

# ============================================================================
# LLM Configuration
# ============================================================================

class LLMModelConfig(BaseModel):
    """Configuration for a single LLM model."""
    name: str = Field(..., description="Model name")
    max_tokens: int = Field(default=4096, ge=1, description="Maximum tokens")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Top-p sampling")
    frequency_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(default=None, ge=-2.0, le=2.0)

class LLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""
    api_key: str = Field(..., description="API key")
    base_url: Optional[str] = Field(default=None, description="Base URL")
    models: list[LLMModelConfig] = Field(..., description="Available models")
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retries")
    rate_limit: Optional[int] = Field(default=None, ge=1, description="Rate limit per minute")

class LLMConfig(BaseModel):
    """Configuration for LLM providers."""
    providers: dict[str, LLMProviderConfig] = Field(..., description="LLM providers")
    primary_provider: str = Field(..., description="Primary provider name")
    fallback_providers: Optional[list[str]] = Field(default=None, description="Fallback providers")
    cross_validation_enabled: bool = Field(default=False, description="Enable cross-validation")
    cache_enabled: bool = Field(default=True, description="Enable response caching")
    cache_ttl: int = Field(default=3600, ge=0, description="Cache TTL in seconds")

# ============================================================================
# Push Configuration
# ============================================================================

class PushChannelConfig(BaseModel):
    """Configuration for a single push channel."""
    enabled: bool = Field(default=True, description="Whether channel is enabled")
    api_key: Optional[str] = Field(default=None, description="API key or token")
    bot_token: Optional[str] = Field(default=None, description="Bot token")
    chat_id: Optional[str] = Field(default=None, description="Chat ID")
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL")
    from_email: Optional[str] = Field(default=None, description="From email address")
    smtp_host: Optional[str] = Field(default=None, description="SMTP host")
    smtp_port: Optional[int] = Field(default=None, ge=1, le=65535, description="SMTP port")
    smtp_username: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    use_tls: bool = Field(default=True, description="Use TLS for SMTP")

class PushConfig(BaseModel):
    """Configuration for push notification channels."""
    channels: dict[str, PushChannelConfig] = Field(..., description="Push channels")
    default_channel: Optional[str] = Field(default=None, description="Default channel")
    retry_count: int = Field(default=2, ge=0, le=10, description="Retry count")
    retry_delay: int = Field(default=5, ge=1, le=60, description="Retry delay in seconds")
    timeout: int = Field(default=10, ge=1, le=60, description="Request timeout")

# ============================================================================
# Prompt Templates Configuration
# ============================================================================

class PromptTemplateConfig(BaseModel):
    """Configuration for a single prompt template."""
    data_type: str = Field(..., description="Data type this template handles")
    template_name: str = Field(..., description="Template name")
    system_prompt: str = Field(..., description="System prompt")
    user_prompt_template: str = Field(..., description="User prompt template with placeholders")
    required_context: list[str] = Field(default_factory=list, description="Required context variables")
    conditional_sections: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Conditional sections"
    )

class ContextVariableConfig(BaseModel):
    """Configuration for a context variable."""
    name: str = Field(..., description="Variable name")
    source: str = Field(..., description="Variable source (database, config, runtime)")
    required: bool = Field(default=False, description="Whether variable is required")

class RenderingConfig(BaseModel):
    """Configuration for template rendering."""
    strict_mode: bool = Field(default=False, description="Strict mode for missing variables")
    escape_html: bool = Field(default=False, description="Escape HTML in output")
    trim_blocks: bool = Field(default=True, description="Trim blocks")
    lstrip_blocks: bool = Field(default=True, description="Left-strip blocks")

class PromptTemplatesConfig(BaseModel):
    """Configuration for all prompt templates."""
    templates: list[PromptTemplateConfig] = Field(..., description="Prompt templates")
    context_variables: Optional[list[ContextVariableConfig]] = Field(
        default=None,
        description="Context variable definitions"
    )
    rendering: Optional[RenderingConfig] = Field(default=None, description="Rendering settings")

# ============================================================================
# External Tools Configuration
# ============================================================================

class SourceType(str, Enum):
    """External tool source type."""
    GITHUB = "github"
    LOCAL = "local"

class IntegrationMethod(str, Enum):
    """External tool integration method."""
    IMPORT = "import"
    COMMAND_LINE = "command_line"

class ExternalToolConfig(BaseModel):
    """Configuration for a single external tool."""
    tool_id: str = Field(..., description="Unique tool identifier")
    tool_name: str = Field(..., description="Tool name")
    source_type: SourceType = Field(..., description="Source type")
    source_url: Optional[str] = Field(default=None, description="Source URL for GitHub")
    local_path: Optional[str] = Field(default=None, description="Local path")
    integration_method: IntegrationMethod = Field(..., description="Integration method")
    risk_warning: str = Field(default="", description="Risk warning message")
    enabled: bool = Field(default=True, description="Whether tool is enabled")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")

    @model_validator(mode='after')
    def validate_source(self) -> 'ExternalToolConfig':
        """Validate source configuration."""
        if self.source_type == SourceType.GITHUB and not self.source_url:
            raise ValueError("source_url is required for GitHub source type")
        if self.source_type == SourceType.LOCAL and not self.local_path:
            raise ValueError("local_path is required for local source type")
        return self

class ExternalToolsConfig(BaseModel):
    """Configuration for all external tools."""
    tools: list[ExternalToolConfig] = Field(default_factory=list, description="External tools")

# ============================================================================
# Event Bus Configuration
# ============================================================================

class RedisConfig(BaseModel):
    """Redis connection configuration."""
    url: str = Field(..., description="Redis URL")
    password: Optional[str] = Field(default=None, description="Redis password")
    pool_min_size: int = Field(default=5, ge=1, le=100, description="Minimum pool size")
    pool_max_size: int = Field(default=20, ge=1, le=1000, description="Maximum pool size")
    connection_timeout: int = Field(default=30, ge=1, le=300, description="Connection timeout")
    socket_timeout: int = Field(default=30, ge=1, le=300, description="Socket timeout")
    socket_keepalive: bool = Field(default=True, description="Enable socket keepalive")
    retry_on_timeout: bool = Field(default=True, description="Retry on timeout")
    health_check_interval: int = Field(default=30, ge=1, le=300, description="Health check interval")

class TopicConfig(BaseModel):
    """Event bus topic configuration."""
    name: str = Field(..., description="Topic name")
    description: Optional[str] = Field(default=None, description="Topic description")
    retention_seconds: int = Field(default=3600, ge=0, description="Message retention")
    max_queue_depth: int = Field(default=10000, ge=1, description="Maximum queue depth")

class DeadLetterQueueConfig(BaseModel):
    """Dead letter queue configuration."""
    enabled: bool = Field(default=True, description="Enable DLQ")
    max_retry_attempts: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(default=60, ge=1, description="Retry delay")
    retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, description="Backoff multiplier")
    retention_days: int = Field(default=7, ge=1, description="Retention days")
    max_size: int = Field(default=10000, ge=1, description="Maximum DLQ size")

class EventBusConfig(BaseModel):
    """Event bus configuration."""
    redis: RedisConfig = Field(..., description="Redis configuration")
    topics: list[TopicConfig] = Field(..., description="Topic configurations")
    dead_letter_queue: DeadLetterQueueConfig = Field(..., description="DLQ configuration")

# ============================================================================
# Retention Policy Configuration
# ============================================================================

class RetentionPolicyConfig(BaseModel):
    """Configuration for a single retention policy."""
    data_type: str = Field(..., description="Data type")
    retention_days: int = Field(..., ge=1, description="Retention period in days")
    archive_before_delete: bool = Field(default=True, description="Archive before deletion")
    soft_delete: bool = Field(default=False, description="Use soft delete")
    cleanup_priority: str = Field(default="low", description="Cleanup priority")

class ArchiveConfig(BaseModel):
    """Archive configuration."""
    enabled: bool = Field(default=True, description="Enable archiving")
    location: str = Field(default="archive/", description="Archive location")
    compression: str = Field(default="gzip", description="Compression method")
    compression_level: int = Field(default=6, ge=1, le=9, description="Compression level")
    max_archive_size_mb: int = Field(default=1000, ge=1, description="Max archive size in MB")

class BackupConfig(BaseModel):
    """Backup configuration."""
    enabled: bool = Field(default=True, description="Enable backup")
    location: str = Field(default="backup/", description="Backup location")
    retention_days: int = Field(default=7, ge=1, description="Backup retention days")

class ExecutionConfig(BaseModel):
    """Cleanup execution configuration."""
    batch_size: int = Field(default=1000, ge=1, description="Batch size")
    max_execution_time_minutes: int = Field(default=60, ge=1, description="Max execution time")
    dry_run: bool = Field(default=False, description="Dry run mode")

class RetentionPoliciesConfig(BaseModel):
    """Configuration for all retention policies."""
    policies: list[RetentionPolicyConfig] = Field(..., description="Retention policies")
    cleanup_schedule: str = Field(default="0 3 * * *", description="Cleanup schedule (cron)")
    archive: Optional[ArchiveConfig] = Field(default=None, description="Archive settings")
    backup: Optional[BackupConfig] = Field(default=None, description="Backup settings")
    execution: Optional[ExecutionConfig] = Field(default=None, description="Execution settings")

# ============================================================================
# Configuration Type Mapping
# ============================================================================

CONFIG_SCHEMAS: dict[str, Type[BaseModel]] = {
    'fetch_sources.yaml': FetchSourcesConfig,
    'llm_config.yaml': LLMConfig,
    'push_config.yaml': PushConfig,
    'prompt_templates.yaml': PromptTemplatesConfig,
    'external_tools.yaml': ExternalToolsConfig,
    'event_bus.yaml': EventBusConfig,
    'retention_policy.yaml': RetentionPoliciesConfig,
}
