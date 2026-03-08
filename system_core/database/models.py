"""
Database models for OpenFi Lite system.

This module defines all SQLAlchemy ORM models for the PostgreSQL database,
including users, EA profiles, push configurations, trades, fetch sources, and LLM logs.
"""

from datetime import datetime

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    ARRAY,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    """User account table"""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="trader")
    must_change_password = Column(Boolean, default=False, nullable=False)  # Force password change on next login
    
    # Timezone settings (for future multi-user support)
    # 时区设置（为未来多用户功能预留）
    timezone = Column(String(50), nullable=False, default="Asia/Shanghai")  # IANA timezone
    datetime_format = Column(String(50), default="%Y-%m-%d %H:%M:%S")
    show_timezone_name = Column(Boolean, default=True)
    use_12_hour_format = Column(Boolean, default=False)
    
    # Parent-child relationship (for future sub-account support)
    # 主子账户关系（为未来子账户功能预留）
    parent_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    
    # Permissions (for future sub-account permission control)
    # 权限控制（为未来子账户权限管理预留）
    # JSONB format: {
    #   "api_access": true,
    #   "llm_access": true,
    #   "trading_access": false,
    #   "allowed_brokers": ["broker_uuid_1", "broker_uuid_2"],  # Restrict to specific brokers
    #   "allowed_trading_accounts": ["account_uuid_1"],
    #   ...
    # }
    permissions = Column(JSONB, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    ea_profiles = relationship("EAProfile", back_populates="user", cascade="all, delete-orphan")
    push_configs = relationship("PushConfig", back_populates="user", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="user")
    
    # Parent-child relationship (self-referential)
    parent = relationship("User", remote_side=[id], backref="sub_accounts")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"

class EAProfile(Base):
    """Expert Advisor (EA) profile configuration table"""
    
    __tablename__ = "ea_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ea_name = Column(String(100), nullable=False, index=True)
    symbols = Column(ARRAY(String), nullable=False)
    timeframe = Column(String(10), nullable=False)
    risk_per_trade = Column(Numeric(5, 4), nullable=False)
    max_positions = Column(Integer, nullable=False, default=1)
    max_total_risk = Column(Numeric(5, 4), nullable=False)
    strategy_logic_description = Column(Text)
    auto_execution = Column(Boolean, default=False, nullable=False)
    
    # Circuit Breaker thresholds (optional, uses defaults if not set)
    max_consecutive_losses = Column(Integer, nullable=True, default=3)
    max_consecutive_failures = Column(Integer, nullable=True, default=5)
    loss_time_window_seconds = Column(Integer, nullable=True, default=300)  # 5 minutes
    
    version = Column(Integer, nullable=False, default=1)  # Optimistic locking
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    user = relationship("User", back_populates="ea_profiles")
    trades = relationship("Trade", back_populates="ea_profile")
    
    def __repr__(self):
        return f"<EAProfile(id={self.id}, ea_name={self.ea_name}, user_id={self.user_id})>"

class PushConfig(Base):
    """Push notification configuration table"""
    
    __tablename__ = "push_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(20), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    credentials = Column(JSONB, nullable=False)
    template = Column(Text)
    alert_rules = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="push_configs")
    
    def __repr__(self):
        return f"<PushConfig(id={self.id}, user_id={self.user_id}, channel={self.channel})>"

class Trade(Base):
    """Trade execution record table"""
    
    __tablename__ = "trades"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    ea_profile_id = Column(UUID(as_uuid=True), ForeignKey("ea_profiles.id"), nullable=False, index=True)
    
    # Broker and trading account (for future multi-broker support)
    # 经纪商和交易账户（为未来多经纪商支持预留）
    broker_id = Column(UUID(as_uuid=True), ForeignKey("brokers.id"), nullable=True, index=True)
    trading_account_id = Column(UUID(as_uuid=True), ForeignKey("trading_accounts.id"), nullable=True, index=True)
    
    signal_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    direction = Column(String(10), nullable=False)
    volume = Column(Numeric(10, 2), nullable=False)
    entry_price = Column(Numeric(20, 5), nullable=False)
    stop_loss = Column(Numeric(20, 5))
    take_profit = Column(Numeric(20, 5))
    execution_price = Column(Numeric(20, 5))
    broker_order_id = Column(String(100))
    status = Column(String(20), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)  # Optimistic locking
    executed_at = Column(DateTime(timezone=True), index=True)
    closed_at = Column(DateTime(timezone=True))
    pnl = Column(Numeric(20, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="trades")
    ea_profile = relationship("EAProfile", back_populates="trades")
    broker = relationship("Broker", backref="trades")
    trading_account = relationship("TradingAccount", backref="trades")
    
    def __repr__(self):
        return f"<Trade(id={self.id}, symbol={self.symbol}, direction={self.direction}, status={self.status})>"

class FetchSource(Base):
    """Data fetch source configuration table"""
    
    __tablename__ = "fetch_sources"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(String(50), unique=True, nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    api_endpoint = Column(Text, nullable=False)
    credentials = Column(JSONB)
    schedule_type = Column(String(20), nullable=False)
    schedule_config = Column(JSONB, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    last_fetch_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<FetchSource(id={self.id}, source_id={self.source_id}, source_type={self.source_type})>"

class LLMLog(Base):
    """LLM API call logging table"""
    
    __tablename__ = "llm_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)
    latency_ms = Column(Integer)
    status = Column(String(20), nullable=False, index=True)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<LLMLog(id={self.id}, provider={self.provider}, model={self.model}, status={self.status})>"

# ============================================
# Broker and Trading Account Models
# 经纪商和交易账户模型（为未来多用户功能预留）
# ============================================

class Broker(Base):
    """
    Broker configuration table (Reserved for future multi-user support)
    经纪商配置表（为未来多用户功能预留）
    
    This table stores broker connection configurations.
    In Pro version, main accounts can restrict sub-accounts to specific brokers.
    """
    
    __tablename__ = "brokers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Broker identification
    broker_name = Column(String(100), nullable=False, index=True)  # e.g., "IC Markets", "OANDA"
    broker_type = Column(String(50), nullable=False, index=True)   # e.g., "MT4", "MT5", "cTrader", "API"
    
    # Connection configuration (JSONB for flexibility)
    # 连接配置（JSONB 格式，灵活存储不同经纪商的配置）
    # Example: {"server": "ICMarkets-Demo", "api_url": "https://api.broker.com", ...}
    connection_config = Column(JSONB, nullable=False)
    
    # API credentials (encrypted in production)
    # API 凭证（生产环境需加密）
    # Example: {"api_key": "xxx", "api_secret": "xxx", "account_id": "xxx"}
    credentials = Column(JSONB, nullable=False)
    
    # Broker capabilities and limits
    # 经纪商能力和限制
    # Example: {"max_leverage": 500, "min_lot_size": 0.01, "supported_symbols": [...]}
    capabilities = Column(JSONB, default={})
    
    # Status
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    is_demo = Column(Boolean, default=False, nullable=False)  # Demo or Live account
    
    # Metadata
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    trading_accounts = relationship("TradingAccount", back_populates="broker", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Broker(id={self.id}, broker_name={self.broker_name}, broker_type={self.broker_type})>"

class TradingAccount(Base):
    """
    Trading account table (Reserved for future multi-user support)
    交易账户表（为未来多用户功能预留）
    
    Links users to broker accounts with specific permissions.
    Main accounts can assign specific trading accounts to sub-accounts.
    """
    
    __tablename__ = "trading_accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User and Broker relationship
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id = Column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Account identification
    account_number = Column(String(100), nullable=False, index=True)
    account_name = Column(String(100), nullable=False)
    
    # Account type and status
    account_type = Column(String(20), nullable=False, default="demo")  # demo, live
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Trading limits (for sub-account control)
    # 交易限制（用于子账户控制）
    # Example: {
    #   "max_daily_trades": 10,
    #   "max_position_size": 1.0,
    #   "max_leverage": 100,
    #   "allowed_symbols": ["EURUSD", "GBPUSD"],
    #   "max_daily_loss": 1000.0,
    #   "max_total_exposure": 5000.0
    # }
    trading_limits = Column(JSONB, default={})
    
    # Account balance and statistics (cached, updated periodically)
    # 账户余额和统计（缓存，定期更新）
    balance = Column(Numeric(20, 2), default=0.0)
    equity = Column(Numeric(20, 2), default=0.0)
    margin_used = Column(Numeric(20, 2), default=0.0)
    margin_free = Column(Numeric(20, 2), default=0.0)
    last_sync_at = Column(DateTime(timezone=True))
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    user = relationship("User", backref="trading_accounts")
    broker = relationship("Broker", back_populates="trading_accounts")
    
    def __repr__(self):
        return f"<TradingAccount(id={self.id}, account_number={self.account_number}, user_id={self.user_id})>"

class UserBrokerPermission(Base):
    """
    User-Broker permission mapping (Reserved for future multi-user support)
    用户-经纪商权限映射表（为未来多用户功能预留）
    
    Controls which brokers a user (especially sub-accounts) can access.
    Main accounts can restrict sub-accounts to specific brokers only.
    """
    
    __tablename__ = "user_broker_permissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # User and Broker relationship
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id = Column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Permission level
    # 权限级别
    # - "read_only": Can view broker info and account status
    # - "trade": Can execute trades
    # - "manage": Can modify broker configuration (main account only)
    permission_level = Column(String(20), nullable=False, default="read_only")
    
    # Specific permissions (JSONB for flexibility)
    # 具体权限（JSONB 格式）
    # Example: {
    #   "can_open_positions": true,
    #   "can_close_positions": true,
    #   "can_modify_orders": false,
    #   "can_view_history": true,
    #   "allowed_order_types": ["market", "limit"],
    #   "max_order_size": 1.0
    # }
    specific_permissions = Column(JSONB, default={})
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Granted by (for audit trail)
    # 授权人（用于审计）
    granted_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Optional expiration
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="broker_permissions")
    broker = relationship("Broker", backref="user_permissions")
    granted_by = relationship("User", foreign_keys=[granted_by_user_id])
    
    # Unique constraint: one permission record per user-broker pair
    __table_args__ = (
        # Unique constraint removed to allow multiple permission records with different levels
        # Use is_active to manage active permissions
    )
    
    def __repr__(self):
        return f"<UserBrokerPermission(user_id={self.user_id}, broker_id={self.broker_id}, level={self.permission_level})>"

# ============================================
# Core Business Module Models
# ============================================

class Signal(Base):
    """AI-analyzed signal table for storing high-value information"""
    
    __tablename__ = "signals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False)
    source_type = Column(String(50), nullable=False, index=True)
    data_type = Column(String(50), nullable=False)
    content = Column(JSONB, nullable=False)
    relevance_score = Column(Integer, nullable=False)
    potential_impact = Column(
        String(20),
        nullable=False,
        default='low'
    )
    summary = Column(Text, nullable=False)
    suggested_actions = Column(JSONB)
    related_symbols = Column(ARRAY(String(20)))
    confidence = Column(Numeric(5, 4))
    reasoning = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<Signal(id={self.id}, source={self.source}, relevance_score={self.relevance_score})>"

class Notification(Base):
    """Push notification tracking table"""
    
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"), nullable=True)
    channel = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default='pending', index=True)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", backref="notifications")
    signal = relationship("Signal", backref="notifications")
    
    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, channel={self.channel}, status={self.status})>"

class AlertRule(Base):
    """User alert rule configuration table"""
    
    __tablename__ = "alert_rules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_name = Column(String(100), nullable=False)
    min_relevance_score = Column(Integer)
    required_symbols = Column(ARRAY(String(20)))
    required_impact_levels = Column(ARRAY(String(20)))
    time_windows = Column(ARRAY(String(50)))
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    user = relationship("User", backref="alert_rules")
    
    def __repr__(self):
        return f"<AlertRule(id={self.id}, user_id={self.user_id}, rule_name={self.rule_name}, enabled={self.enabled})>"

class CircuitBreakerState(Base):
    """Circuit breaker state tracking table"""
    
    __tablename__ = "circuit_breaker_states"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ea_profile_id = Column(UUID(as_uuid=True), ForeignKey("ea_profiles.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    consecutive_losses = Column(Integer, default=0)
    consecutive_failures = Column(Integer, default=0)
    is_active = Column(Boolean, default=False, nullable=False, index=True)
    triggered_at = Column(DateTime(timezone=True))
    trigger_reason = Column(Text)
    reset_at = Column(DateTime(timezone=True))
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    ea_profile = relationship("EAProfile", backref="circuit_breaker_state")
    
    def __repr__(self):
        return f"<CircuitBreakerState(id={self.id}, ea_profile_id={self.ea_profile_id}, is_active={self.is_active})>"

class AuditLog(Base):
    """Audit log table for compliance and security tracking"""
    
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(UUID(as_uuid=True))
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)
    signature = Column(String(255))  # HMAC-SHA256 signature
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    user = relationship("User", backref="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action={self.action}, resource_type={self.resource_type})>"

class AlertLog(Base):
    """Alert log table for monitoring and alerting history"""
    
    __tablename__ = "alert_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condition = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    component = Column(String(100), nullable=False, index=True)
    message = Column(Text, nullable=False)
    alert_metadata = Column(JSONB)  # Renamed from 'metadata' to avoid SQLAlchemy reserved word
    runbook_url = Column(String(500))
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<AlertLog(id={self.id}, condition={self.condition}, severity={self.severity}, component={self.component})>"

# ============================================
# Multi-Agent System Models
# 多Agent系统模型
# ============================================

class Agent(Base):
    """
    Agent table for multi-agent system
    多Agent系统的Agent表
    
    Each agent is an independent intelligent entity with custom configuration,
    permissions, asset scope, trigger conditions, and push settings.
    """
    
    __tablename__ = "agents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic information
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text)
    
    # Status and priority
    status = Column(String(50), nullable=False, default='inactive', index=True)  # active, inactive, paused, error
    priority = Column(String(50), nullable=False, default='normal')  # low, normal, high, critical
    
    # Owner (link to user)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Organization and categorization
    tags = Column(ARRAY(String), default=[])
    category = Column(String(100), index=True)  # broadcast, fact_check, backtest, forex, crypto, daily, weekly, etc.
    
    # Custom metadata
    agent_metadata = Column(JSONB, default={})  # Renamed from 'metadata' to avoid SQLAlchemy reserved word
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    owner = relationship("User", backref="agents")
    configs = relationship("AgentConfig", back_populates="agent", cascade="all, delete-orphan")
    assets = relationship("AgentAsset", back_populates="agent", cascade="all, delete-orphan")
    triggers = relationship("AgentTrigger", back_populates="agent", cascade="all, delete-orphan")
    push_config = relationship("AgentPushConfig", back_populates="agent", cascade="all, delete-orphan", uselist=False)
    bot_connections = relationship("AgentBotConnection", back_populates="agent", cascade="all, delete-orphan")
    metrics = relationship("AgentMetric", back_populates="agent", cascade="all, delete-orphan")
    logs = relationship("AgentLog", back_populates="agent", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Agent(id={self.id}, name={self.name}, status={self.status}, owner_user_id={self.owner_user_id})>"

class AgentConfig(Base):
    """
    Agent configuration table with versioning
    Agent配置表（带版本控制）
    
    Stores complete agent configuration including permissions, quotas, and settings.
    Each configuration change creates a new version for audit and rollback.
    """
    
    __tablename__ = "agent_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Version control
    version = Column(Integer, nullable=False)
    
    # Configuration (JSONB for flexibility)
    # Structure: {
    #   "permissions": {"info_retrieval": "full_access", "ai_analysis": "full_access", ...},
    #   "quotas": {"max_api_calls_per_hour": 1000, "max_llm_tokens_per_day": 100000, ...},
    #   "settings": {...}
    # }
    config_json = Column(JSONB, nullable=False)
    
    # Audit information
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by = Column(String(255), nullable=False)  # User who made the change
    change_description = Column(Text)
    
    # Relationships
    agent = relationship("Agent", back_populates="configs")
    
    # Unique constraint: one version per agent
    __table_args__ = (
        # Unique constraint on agent_id and version
    )
    
    def __repr__(self):
        return f"<AgentConfig(id={self.id}, agent_id={self.agent_id}, version={self.version})>"

class AgentAsset(Base):
    """
    Agent asset portfolio table
    Agent资产组合表
    
    Defines which trading symbols an agent monitors and their weights.
    """
    
    __tablename__ = "agent_assets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Asset information
    symbol = Column(String(50), nullable=False, index=True)  # XAUUSD, BTCUSD, EURUSD, etc.
    weight = Column(Numeric(5, 4), nullable=False)  # 0.0 - 1.0
    category = Column(String(50), nullable=False, index=True)  # forex, crypto, commodities, indices, stocks
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    agent = relationship("Agent", back_populates="assets")
    
    # Unique constraint: one symbol per agent
    __table_args__ = (
        # Unique constraint on agent_id and symbol
    )
    
    def __repr__(self):
        return f"<AgentAsset(id={self.id}, agent_id={self.agent_id}, symbol={self.symbol}, weight={self.weight})>"

class AgentTrigger(Base):
    """
    Agent trigger configuration table
    Agent触发配置表
    
    Defines trigger conditions for an agent (keywords, factors, price, time, etc.).
    """
    
    __tablename__ = "agent_triggers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Trigger type
    trigger_type = Column(String(50), nullable=False, index=True)  # keywords, factors, price, price_change, time, manual
    
    # Trigger configuration (JSONB for flexibility)
    # Structure depends on trigger_type:
    # - keywords: {"enabled": true, "keywords": ["gold", "fed"], "priority": "mandatory"}
    # - factors: {"enabled": true, "factor_config_file": "path/to/config.yaml"}
    # - price: {"enabled": true, "price_levels": [{"symbol": "XAUUSD", "price": 2000, "direction": "above"}]}
    # - etc.
    trigger_config_json = Column(JSONB, nullable=False)
    
    # Status
    enabled = Column(Boolean, default=True, nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    agent = relationship("Agent", back_populates="triggers")
    
    def __repr__(self):
        return f"<AgentTrigger(id={self.id}, agent_id={self.agent_id}, trigger_type={self.trigger_type}, enabled={self.enabled})>"

class AgentPushConfig(Base):
    """
    Agent push notification configuration table
    Agent推送通知配置表
    
    Defines push channels, frequency limits, quiet hours, and message templates.
    """
    
    __tablename__ = "agent_push_configs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Push configuration (JSONB for flexibility)
    # Structure: {
    #   "channels": ["telegram", "discord"],
    #   "frequency_limits": {"max_pushes_per_hour": 10, "max_pushes_per_day": 100},
    #   "quiet_hours": {"enabled": true, "start_time": "22:00", "end_time": "08:00", "timezone": "Asia/Shanghai"},
    #   "message_templates": {"keyword_trigger": "...", "factor_trigger": "..."},
    #   "content_options": {"include_ai_analysis": true, "include_ea_recommendation": false, ...}
    # }
    push_config_json = Column(JSONB, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    agent = relationship("Agent", back_populates="push_config")
    
    def __repr__(self):
        return f"<AgentPushConfig(id={self.id}, agent_id={self.agent_id})>"

class AgentBotConnection(Base):
    """
    Agent bot connection table
    Agent Bot连接表
    
    Links agents to specific bot accounts (Telegram, Discord, etc.) for message delivery.
    Each agent can have multiple bot connections (max 5).
    """
    
    __tablename__ = "agent_bot_connections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Bot information
    bot_type = Column(String(50), nullable=False, index=True)  # telegram, discord, slack, webhook
    credentials_encrypted = Column(Text, nullable=False)  # Encrypted bot credentials (token, webhook_url, etc.)
    target_channel = Column(String(255), nullable=False)  # chat_id, channel_id, etc.
    
    # Status and health
    status = Column(String(50), nullable=False, default='inactive', index=True)  # active, inactive, error
    health_check_interval = Column(Integer, nullable=False, default=300)  # seconds
    last_health_check = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    agent = relationship("Agent", back_populates="bot_connections")
    
    def __repr__(self):
        return f"<AgentBotConnection(id={self.id}, agent_id={self.agent_id}, bot_type={self.bot_type}, status={self.status})>"

class AgentMetric(Base):
    """
    Agent metrics table for performance monitoring
    Agent指标表（性能监控）
    
    Stores time-series metrics for agent performance tracking.
    """
    
    __tablename__ = "agent_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Metric information
    metric_type = Column(String(100), nullable=False, index=True)  # trigger_count, push_count, error_count, response_time, etc.
    metric_value = Column(Numeric(20, 4), nullable=False)
    
    # Additional tags for filtering
    tags = Column(JSONB)  # {"trigger_type": "keyword", "symbol": "XAUUSD", ...}
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Relationships
    agent = relationship("Agent", back_populates="metrics")
    
    def __repr__(self):
        return f"<AgentMetric(id={self.id}, agent_id={self.agent_id}, metric_type={self.metric_type}, metric_value={self.metric_value})>"

class AgentLog(Base):
    """
    Agent log table for debugging and audit
    Agent日志表（调试和审计）
    
    Stores detailed logs for agent operations.
    """
    
    __tablename__ = "agent_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Log information
    log_level = Column(String(50), nullable=False, index=True)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    
    # Additional context
    context = Column(JSONB)  # {"trigger_type": "keyword", "symbol": "XAUUSD", "error": "...", ...}
    
    # Timestamp
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Relationships
    agent = relationship("Agent", back_populates="logs")
    
    def __repr__(self):
        return f"<AgentLog(id={self.id}, agent_id={self.agent_id}, log_level={self.log_level}, timestamp={self.timestamp})>"
