"""
Agent System Pydantic Schemas

Request and response schemas for Agent API endpoints.
"""

from typing import Optional, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, validator

from system_core.agent_system.models import (
    AgentStatus,
    AgentPriority,
    PermissionLevel,
    AssetCategory,
    TriggerType,
    BotType,
    ConnectionStatus,
    AgentPermissions,
    ResourceQuotas,
    AssetWeight,
    AssetPortfolio,
    TriggerConfig,
    PushConfig,
    BotConnection,
)

# ============================================
# Agent CRUD Schemas
# ============================================

class AgentCreateRequest(BaseModel):
    """Request schema for creating an agent."""
    
    name: str = Field(..., min_length=1, max_length=100, description="Agent name (unique)")
    description: Optional[str] = Field(None, max_length=500, description="Agent description")
    status: AgentStatus = Field(AgentStatus.INACTIVE, description="Initial agent status")
    priority: AgentPriority = Field(AgentPriority.NORMAL, description="Agent priority")
    owner_user_id: Optional[UUID] = Field(None, description="Owner user ID (defaults to current user)")
    category: Optional[str] = Field(None, max_length=50, description="Agent category")
    tags: list[str] = Field(default_factory=list, description="Agent tags")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    config: Optional[dict[str, Any]] = Field(None, description="Agent configuration")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate agent name."""
        if not v or not v.strip():
            raise ValueError("Agent name cannot be empty")
        return v.strip()

    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags list."""
        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")
        return [tag.strip() for tag in v if tag.strip()]

class AgentUpdateRequest(BaseModel):
    """Request schema for updating an agent."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    priority: Optional[AgentPriority] = None
    category: Optional[str] = Field(None, max_length=50)
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None
    
    @validator('name')
    def validate_name(cls, v):
        """Validate agent name."""
        if v is not None and (not v or not v.strip()):
            raise ValueError("Agent name cannot be empty")
        return v.strip() if v else v
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags list."""
        if v is not None and len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")
        return [tag.strip() for tag in v if tag.strip()] if v else v

class AgentResponse(BaseModel):
    """Response schema for agent."""
    
    id: UUID
    name: str
    description: Optional[str]
    status: AgentStatus
    priority: AgentPriority
    owner_user_id: UUID
    category: Optional[str]
    tags: list[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class AgentListResponse(BaseModel):
    """Response schema for agent list."""
    
    agents: list[AgentResponse]
    total: int
    page: int
    page_size: int

# ============================================
# Agent Configuration Schemas
# ============================================

class AgentConfigRequest(BaseModel):
    """Request schema for agent configuration."""
    
    permissions: Optional[AgentPermissions] = None
    asset_portfolio: Optional[AssetPortfolio] = None
    trigger_config: Optional[TriggerConfig] = None
    push_config: Optional[PushConfig] = None
    quotas: Optional[ResourceQuotas] = None
    
    @validator('asset_portfolio')
    def validate_asset_portfolio(cls, v):
        """Validate asset portfolio."""
        if v is not None:
            # Check total weight
            total_weight = sum(asset.weight for asset in v.assets)
            if total_weight > 1.0:
                raise ValueError(f"Total asset weight ({total_weight}) exceeds 1.0")
            
            # Check individual weights
            for asset in v.assets:
                if asset.weight < 0.0 or asset.weight > 1.0:
                    raise ValueError(
                        f"Asset {asset.symbol} weight ({asset.weight}) "
                        f"must be between 0.0 and 1.0"
                    )
        
        return v
    
    @validator('quotas')
    def validate_quotas(cls, v):
        """Validate resource quotas."""
        if v is not None:
            if v.max_api_calls_per_hour < 0:
                raise ValueError("max_api_calls_per_hour must be non-negative")
            if v.max_llm_tokens_per_day < 0:
                raise ValueError("max_llm_tokens_per_day must be non-negative")
            if v.max_push_messages_per_hour < 0:
                raise ValueError("max_push_messages_per_hour must be non-negative")
            if v.max_concurrent_operations < 1:
                raise ValueError("max_concurrent_operations must be at least 1")
        
        return v

class AgentConfigResponse(BaseModel):
    """Response schema for agent configuration."""
    
    id: UUID
    agent_id: UUID
    version: int
    permissions: AgentPermissions
    asset_portfolio: AssetPortfolio
    trigger_config: TriggerConfig
    push_config: PushConfig
    quotas: ResourceQuotas
    created_at: datetime
    created_by: Optional[UUID]
    change_description: Optional[str]
    
    class Config:
        from_attributes = True

class AgentConfigVersionResponse(BaseModel):
    """Response schema for configuration version list."""
    
    versions: list[AgentConfigResponse]
    total: int

# ============================================
# Asset Management Schemas
# ============================================

class AssetWeightRequest(BaseModel):
    """Request schema for asset weight."""
    
    symbol: str = Field(..., min_length=1, max_length=20)
    weight: float = Field(..., ge=0.0, le=1.0)
    category: AssetCategory
    
    @validator('symbol')
    def validate_symbol(cls, v):
        """Validate asset symbol."""
        return v.strip().upper()

class AssetWeightResponse(BaseModel):
    """Response schema for asset weight."""
    
    symbol: str
    weight: float
    category: AssetCategory
    
    class Config:
        from_attributes = True

class AssetPortfolioRequest(BaseModel):
    """Request schema for asset portfolio."""
    
    assets: list[AssetWeightRequest]
    
    @validator('assets')
    def validate_assets(cls, v):
        """Validate asset portfolio."""
        if len(v) > 50:
            raise ValueError("Maximum 50 assets allowed per agent")
        
        # Check total weight
        total_weight = sum(asset.weight for asset in v)
        if total_weight > 1.0:
            raise ValueError(f"Total asset weight ({total_weight}) exceeds 1.0")
        
        # Check for duplicate symbols
        symbols = [asset.symbol for asset in v]
        if len(symbols) != len(set(symbols)):
            raise ValueError("Duplicate asset symbols not allowed")
        
        return v

class AssetPortfolioResponse(BaseModel):
    """Response schema for asset portfolio."""
    
    assets: list[AssetWeightResponse]
    total_weight: float

# ============================================
# Trigger Configuration Schemas
# ============================================

class TriggerConfigRequest(BaseModel):
    """Request schema for trigger configuration."""
    
    keywords: Optional[dict[str, Any]] = None
    factors: Optional[dict[str, Any]] = None
    price: Optional[dict[str, Any]] = None
    price_change: Optional[dict[str, Any]] = None
    time: Optional[dict[str, Any]] = None
    manual: Optional[dict[str, Any]] = None

class TriggerConfigResponse(BaseModel):
    """Response schema for trigger configuration."""
    
    keywords: dict[str, Any]
    factors: dict[str, Any]
    price: dict[str, Any]
    price_change: dict[str, Any]
    time: dict[str, Any]
    manual: dict[str, Any]
    
    class Config:
        from_attributes = True

# ============================================
# Push Configuration Schemas
# ============================================

class PushConfigRequest(BaseModel):
    """Request schema for push configuration."""
    
    channels: Optional[list[str]] = None
    frequency_limits: Optional[dict[str, Any]] = None
    quiet_hours: Optional[dict[str, Any]] = None
    message_templates: Optional[dict[str, Any]] = None
    content_options: Optional[dict[str, Any]] = None
    
    @validator('channels')
    def validate_channels(cls, v):
        """Validate push channels."""
        if v is not None:
            valid_channels = ["telegram", "discord", "feishu", "wechat_work", "email"]
            for channel in v:
                if channel not in valid_channels:
                    raise ValueError(f"Invalid channel: {channel}")
        return v

class PushConfigResponse(BaseModel):
    """Response schema for push configuration."""
    
    channels: list[str]
    frequency_limits: dict[str, Any]
    quiet_hours: dict[str, Any]
    message_templates: dict[str, Any]
    content_options: dict[str, Any]
    
    class Config:
        from_attributes = True

# ============================================
# Bot Connection Schemas
# ============================================

class BotConnectionRequest(BaseModel):
    """Request schema for bot connection."""
    
    bot_type: BotType
    credentials: dict[str, str] = Field(..., description="Bot credentials (will be encrypted)")
    target_channel: str = Field(..., min_length=1, max_length=200)
    health_check_interval: int = Field(300, ge=60, le=3600, description="Health check interval in seconds")
    
    @validator('credentials')
    def validate_credentials(cls, v, values):
        """Validate bot credentials based on bot type."""
        bot_type = values.get('bot_type')
        
        if bot_type == BotType.TELEGRAM:
            if 'bot_token' not in v or 'chat_id' not in v:
                raise ValueError("Telegram bot requires 'bot_token' and 'chat_id'")
        elif bot_type == BotType.DISCORD:
            if 'webhook_url' not in v:
                raise ValueError("Discord bot requires 'webhook_url'")
        elif bot_type == BotType.SLACK:
            if 'webhook_url' not in v:
                raise ValueError("Slack bot requires 'webhook_url'")
        elif bot_type == BotType.WEBHOOK:
            if 'url' not in v:
                raise ValueError("Webhook bot requires 'url'")
        
        return v

class BotConnectionResponse(BaseModel):
    """Response schema for bot connection."""
    
    id: UUID
    agent_id: UUID
    bot_type: BotType
    target_channel: str
    status: ConnectionStatus
    health_check_interval: int
    last_health_check: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class BotConnectionListResponse(BaseModel):
    """Response schema for bot connection list."""
    
    connections: list[BotConnectionResponse]
    total: int

# ============================================
# Monitoring Schemas
# ============================================

class AgentStatusResponse(BaseModel):
    """Response schema for agent status."""
    
    agent_id: UUID
    status: AgentStatus
    last_trigger_time: Optional[datetime]
    total_triggers: int
    successful_triggers: int
    failed_triggers: int
    last_error: Optional[str]
    uptime_seconds: float

class AgentMetricResponse(BaseModel):
    """Response schema for agent metric."""
    
    id: UUID
    agent_id: UUID
    metric_type: str
    metric_value: float
    tags: dict[str, Any]
    timestamp: datetime
    
    class Config:
        from_attributes = True

class AgentMetricsResponse(BaseModel):
    """Response schema for agent metrics list."""
    
    metrics: list[AgentMetricResponse]
    total: int
    time_range: dict[str, str]

class AgentLogResponse(BaseModel):
    """Response schema for agent log."""
    
    id: UUID
    agent_id: UUID
    log_level: str
    message: str
    context: dict[str, Any]
    timestamp: datetime
    
    class Config:
        from_attributes = True

class AgentLogsResponse(BaseModel):
    """Response schema for agent logs list."""
    
    logs: list[AgentLogResponse]
    total: int
    page: int
    page_size: int

# ============================================
# State Management Schemas
# ============================================

class AgentStateChangeRequest(BaseModel):
    """Request schema for changing agent state."""
    
    status: AgentStatus
    reason: Optional[str] = Field(None, max_length=200)

class AgentStateChangeResponse(BaseModel):
    """Response schema for state change."""
    
    agent_id: UUID
    old_status: AgentStatus
    new_status: AgentStatus
    changed_at: datetime
    reason: Optional[str]

# ============================================
# Import/Export Schemas
# ============================================

class AgentExportResponse(BaseModel):
    """Response schema for agent export."""
    
    agent: AgentResponse
    config: AgentConfigResponse
    format: str  # "json" or "yaml"
    exported_at: datetime

class AgentImportRequest(BaseModel):
    """Request schema for agent import."""
    
    data: dict[str, Any]
    format: str = Field("json", pattern="^(json|yaml)$")
    conflict_resolution: str = Field(
        "skip",
        pattern="^(skip|overwrite|rename)$",
        description="How to handle name conflicts"
    )

class AgentImportResponse(BaseModel):
    """Response schema for agent import."""
    
    imported_agents: list[UUID]
    skipped_agents: list[str]
    errors: list[str]
    total_imported: int
    total_skipped: int

# ============================================
# Validation Schemas
# ============================================

class ConfigValidationRequest(BaseModel):
    """Request schema for configuration validation."""
    
    config: AgentConfigRequest

class ConfigValidationResponse(BaseModel):
    """Response schema for configuration validation."""
    
    valid: bool
    errors: list[str]
    warnings: list[str]

# ============================================
# Error Response Schema
# ============================================

class ErrorResponse(BaseModel):
    """Standard error response schema."""
    
    error_code: str
    message: str
    details: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ============================================
# Agent List Response Schema
# ============================================

class AgentListResponse(BaseModel):
    """Response schema for listing agents."""
    
    agents: list[AgentResponse] = Field(..., description="List of agents")
    total: int = Field(..., description="Total number of agents")
    limit: int = Field(..., description="Results limit")
    offset: int = Field(..., description="Results offset")
    
    class Config:
        from_attributes = True

# ============================================
# Agent State Change Schema
# ============================================

class AgentStateChangeRequest(BaseModel):
    """Request schema for changing agent state."""
    
    new_state: AgentStatus = Field(..., description="New agent state")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for state change")
    
    class Config:
        from_attributes = True

# ============================================
# Agent Clone Schema
# ============================================

class AgentCloneRequest(BaseModel):
    """Request schema for cloning an agent."""
    
    new_name: Optional[str] = Field(None, min_length=1, max_length=100, description="New agent name (auto-generated if not provided)")
    
    @validator('new_name')
    def validate_new_name(cls, v):
        """Validate new agent name."""
        if v and not v.strip():
            raise ValueError("Agent name cannot be empty")
        return v.strip() if v else None
    
    class Config:
        from_attributes = True
