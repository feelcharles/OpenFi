"""
Agent System Data Models

Defines Pydantic models and data classes for the multi-agent system.
These models are used for data validation, serialization, and business logic.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# ============================================
# Enums
# ============================================

class AgentStatus(str, Enum):
    """Agent status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    ERROR = "error"

class AgentPriority(str, Enum):
    """Agent priority enumeration"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class PermissionLevel(str, Enum):
    """Permission level enumeration"""
    NONE = "none"
    READ_ONLY = "read_only"
    FULL_ACCESS = "full_access"

class AssetCategory(str, Enum):
    """Asset category enumeration"""
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITIES = "commodities"
    INDICES = "indices"
    STOCKS = "stocks"

class TriggerType(str, Enum):
    """Trigger type enumeration"""
    KEYWORDS = "keywords"
    FACTORS = "factors"
    PRICE = "price"
    PRICE_CHANGE = "price_change"
    TIME = "time"
    MANUAL = "manual"

class BotType(str, Enum):
    """Bot type enumeration"""
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    WEBHOOK = "webhook"

class ConnectionStatus(str, Enum):
    """Connection status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"

# ============================================
# Configuration Models
# ============================================

class AgentPermissions(BaseModel):
    """Agent permissions configuration"""
    info_retrieval: PermissionLevel = PermissionLevel.FULL_ACCESS
    ai_analysis: PermissionLevel = PermissionLevel.FULL_ACCESS
    backtesting: PermissionLevel = PermissionLevel.NONE
    push_notification: PermissionLevel = PermissionLevel.FULL_ACCESS
    ea_recommendation: PermissionLevel = PermissionLevel.NONE

class ResourceQuotas(BaseModel):
    """Agent resource quotas"""
    max_api_calls_per_hour: int = Field(default=1000, ge=0)
    max_llm_tokens_per_day: int = Field(default=100000, ge=0)
    max_push_messages_per_hour: int = Field(default=100, ge=0)
    max_concurrent_operations: int = Field(default=10, ge=1)
    max_db_query_rate: int = Field(default=100, ge=1)  # queries per second

class AssetWeight(BaseModel):
    """Asset with weight"""
    symbol: str = Field(..., min_length=1, max_length=50)
    weight: float = Field(..., ge=0.0, le=1.0)
    category: AssetCategory
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format"""
        return v.upper().strip()

class AssetPortfolio(BaseModel):
    """Agent asset portfolio"""
    assets: list[AssetWeight] = Field(default_factory=list, max_length=100)
    max_symbols: int = Field(default=100, ge=1, le=100)
    
    @field_validator('assets')
    @classmethod
    def validate_total_weight(cls, v: list[AssetWeight]) -> list[AssetWeight]:
        """Validate total weight <= 1.0"""
        total_weight = sum(asset.weight for asset in v)
        if total_weight > 1.0:
            raise ValueError(f"Total asset weight {total_weight} exceeds 1.0")
        return v

class KeywordTriggerConfig(BaseModel):
    """Keyword trigger configuration"""
    enabled: bool = True
    keywords: list[str] = Field(default_factory=list)
    priority: str = "mandatory"  # mandatory, conditional

class FactorTriggerConfig(BaseModel):
    """Factor trigger configuration"""
    enabled: bool = True
    factor_config_file: Optional[str] = None
    priority: str = "mandatory"

class PriceLevel(BaseModel):
    """Price level configuration"""
    symbol: str
    price: float = Field(..., gt=0)
    direction: str  # above, below
    action: str  # notify, trade, run_ea

class PriceTriggerConfig(BaseModel):
    """Price trigger configuration"""
    enabled: bool = True
    price_levels: list[PriceLevel] = Field(default_factory=list)
    check_interval: int = Field(default=60, ge=1)  # seconds

class PriceChangeThreshold(BaseModel):
    """Price change threshold configuration"""
    symbol: str
    change_value: float
    change_type: str  # absolute, percentage
    time_window: int = Field(default=60, ge=1)  # minutes

class PriceChangeTriggerConfig(BaseModel):
    """Price change trigger configuration"""
    enabled: bool = True
    thresholds: list[PriceChangeThreshold] = Field(default_factory=list)
    check_interval: int = Field(default=60, ge=1)  # seconds

class ScheduledTask(BaseModel):
    """Scheduled task configuration"""
    name: str
    enabled: bool = True
    cron: str  # Cron expression
    timezone: str = "Asia/Shanghai"
    action: str

class TimeTriggerConfig(BaseModel):
    """Time trigger configuration"""
    enabled: bool = True
    scheduled_tasks: list[ScheduledTask] = Field(default_factory=list)

class ManualTriggerConfig(BaseModel):
    """Manual trigger configuration"""
    enabled: bool = True
    allowed_commands: list[str] = Field(default_factory=list)

class TriggerConfig(BaseModel):
    """Complete trigger configuration"""
    keywords: KeywordTriggerConfig = Field(default_factory=KeywordTriggerConfig)
    factors: FactorTriggerConfig = Field(default_factory=FactorTriggerConfig)
    price: PriceTriggerConfig = Field(default_factory=PriceTriggerConfig)
    price_change: PriceChangeTriggerConfig = Field(default_factory=PriceChangeTriggerConfig)
    time: TimeTriggerConfig = Field(default_factory=TimeTriggerConfig)
    manual: ManualTriggerConfig = Field(default_factory=ManualTriggerConfig)

class FrequencyLimits(BaseModel):
    """Push frequency limits"""
    max_pushes_per_hour: int = Field(default=10, ge=0)
    max_pushes_per_day: int = Field(default=100, ge=0)
    allow_critical_override: bool = True

class QuietHours(BaseModel):
    """Quiet hours configuration"""
    enabled: bool = False
    start_time: str = "22:00"  # HH:MM
    end_time: str = "08:00"  # HH:MM
    timezone: str = "Asia/Shanghai"
    allow_critical: bool = True

class ContentOptions(BaseModel):
    """Push content options"""
    include_basic: bool = True  # Always true
    include_ai_analysis: bool = False
    include_ea_recommendation: bool = False
    include_ea_backtest: bool = False
    include_factor_backtest: bool = False
    ea_backtest_mode: str = "simple"  # simple, with_factors

class PushConfig(BaseModel):
    """Push notification configuration"""
    channels: list[str] = Field(default_factory=lambda: ["telegram"])  # telegram, discord, webhook
    frequency_limits: FrequencyLimits = Field(default_factory=FrequencyLimits)
    quiet_hours: QuietHours = Field(default_factory=QuietHours)
    message_templates: dict[str, str] = Field(default_factory=dict)  # trigger_type -> template
    content_options: ContentOptions = Field(default_factory=ContentOptions)

class BotConnection(BaseModel):
    """Bot connection configuration"""
    id: Optional[UUID] = None
    bot_type: BotType
    credentials_encrypted: str
    target_channel: str
    status: ConnectionStatus = ConnectionStatus.INACTIVE
    health_check_interval: int = Field(default=300, ge=60)  # seconds
    last_health_check: Optional[datetime] = None

class AgentConfig(BaseModel):
    """Complete agent configuration"""
    permissions: AgentPermissions = Field(default_factory=AgentPermissions)
    asset_portfolio: AssetPortfolio = Field(default_factory=AssetPortfolio)
    trigger_config: TriggerConfig = Field(default_factory=TriggerConfig)
    push_config: PushConfig = Field(default_factory=PushConfig)
    quotas: ResourceQuotas = Field(default_factory=ResourceQuotas)
    bot_connections: list[BotConnection] = Field(default_factory=list, max_length=5)

# ============================================
# Agent Models
# ============================================

class AgentBase(BaseModel):
    """Base agent model"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: AgentStatus = AgentStatus.INACTIVE
    priority: AgentPriority = AgentPriority.NORMAL
    tags: list[str] = Field(default_factory=list)
    category: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class AgentCreate(AgentBase):
    """Agent creation model"""
    owner_user_id: UUID
    config: Optional[AgentConfig] = None

class AgentUpdate(BaseModel):
    """Agent update model"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[AgentStatus] = None
    priority: Optional[AgentPriority] = None
    tags: Optional[list[str]] = None
    category: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

class Agent(AgentBase):
    """Complete agent model"""
    id: UUID
    owner_user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class AgentWithConfig(Agent):
    """Agent with configuration"""
    config: Optional[AgentConfig] = None

# ============================================
# Execution Models
# ============================================

class TriggerEvent(BaseModel):
    """Trigger event model"""
    agent_id: UUID
    trigger_type: TriggerType
    event_data: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ExecutionResult(BaseModel):
    """Execution result model"""
    success: bool
    agent_id: UUID
    trigger_type: TriggerType
    message: str
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ============================================
# Metrics and Logs
# ============================================

class AgentMetricCreate(BaseModel):
    """Agent metric creation model"""
    agent_id: UUID
    metric_type: str
    metric_value: float
    tags: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AgentLogCreate(BaseModel):
    """Agent log creation model"""
    agent_id: UUID
    log_level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str
    context: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
