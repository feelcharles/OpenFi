"""
Pydantic schemas for Web Backend API responses.

Defines response models for API documentation and validation.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class DashboardMetrics(BaseModel):
    """Dashboard metrics response schema."""
    
    active_data_sources: int = Field(
        ...,
        description="Number of enabled data sources",
        example=4
    )
    fetch_success_rate: float = Field(
        ...,
        description="Success rate of fetch operations in last 24 hours (%)",
        ge=0,
        le=100,
        example=95.5
    )
    ai_processing_queue_depth: int = Field(
        ...,
        description="Current AI processing queue depth",
        ge=0,
        example=12
    )
    active_positions: int = Field(
        ...,
        description="Number of currently open trading positions",
        ge=0,
        example=3
    )
    account_balance: float = Field(
        ...,
        description="Total account balance across all trading accounts",
        example=10000.0
    )
    signals_today: int = Field(
        ...,
        description="Total number of signals generated today",
        ge=0,
        example=45
    )
    high_value_signals_today: int = Field(
        ...,
        description="Number of high-value signals (score > 70) today",
        ge=0,
        example=12
    )
    trades_today: int = Field(
        ...,
        description="Number of trades executed today",
        ge=0,
        example=8
    )
    win_rate_today: float = Field(
        ...,
        description="Win rate for today's trades (%)",
        ge=0,
        le=100,
        example=75.0
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "active_data_sources": 4,
                "fetch_success_rate": 95.5,
                "ai_processing_queue_depth": 12,
                "active_positions": 3,
                "account_balance": 10000.0,
                "signals_today": 45,
                "high_value_signals_today": 12,
                "trades_today": 8,
                "win_rate_today": 75.0
            }
        }

class ComponentStatus(BaseModel):
    """Component status schema."""
    
    status: str = Field(
        ...,
        description="Component health status",
        pattern="^(healthy|degraded|unhealthy)$",
        example="healthy"
    )
    latency_ms: Optional[int] = Field(
        None,
        description="Component latency in milliseconds",
        ge=0,
        example=5
    )
    queue_depth: Optional[int] = Field(
        None,
        description="Queue depth for queue-based components",
        ge=0,
        example=0
    )
    active_tasks: Optional[int] = Field(
        None,
        description="Number of active tasks",
        ge=0,
        example=0
    )
    processing_rate: Optional[int] = Field(
        None,
        description="Processing rate (items/second)",
        ge=0,
        example=0
    )
    pending_signals: Optional[int] = Field(
        None,
        description="Number of pending signals",
        ge=0,
        example=0
    )

class SystemStatus(BaseModel):
    """System status response schema."""
    
    status: str = Field(
        ...,
        description="Overall system health status",
        pattern="^(healthy|degraded|unhealthy)$",
        example="healthy"
    )
    uptime: int = Field(
        ...,
        description="System uptime in seconds",
        ge=0,
        example=86400
    )
    version: str = Field(
        ...,
        description="Application version",
        example="1.0.0"
    )
    components: dict[str, ComponentStatus] = Field(
        ...,
        description="Status of individual system components"
    )
    timestamp: str = Field(
        ...,
        description="Status check timestamp (ISO 8601)",
        example="2024-01-15T10:30:00Z"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "uptime": 86400,
                "version": "1.0.0",
                "components": {
                    "database": {"status": "healthy", "latency_ms": 5},
                    "redis": {"status": "healthy", "latency_ms": 2},
                    "event_bus": {"status": "healthy", "queue_depth": 0}
                },
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }

class SignalResponse(BaseModel):
    """Signal response schema."""
    
    id: str = Field(
        ...,
        description="Signal UUID",
        example="550e8400-e29b-41d4-a716-446655440000"
    )
    source: str = Field(
        ...,
        description="Data source identifier",
        example="bloomberg_news"
    )
    source_type: str = Field(
        ...,
        description="Type of data source",
        example="news"
    )
    data_type: str = Field(
        ...,
        description="Type of data",
        example="news_article"
    )
    relevance_score: int = Field(
        ...,
        description="AI-assessed relevance score (0-100)",
        ge=0,
        le=100,
        example=85
    )
    potential_impact: str = Field(
        ...,
        description="Potential market impact level",
        pattern="^(low|medium|high)$",
        example="high"
    )
    summary: str = Field(
        ...,
        description="AI-generated summary of the signal",
        example="Federal Reserve announces unexpected rate hike, likely to impact USD pairs"
    )
    suggested_actions: Optional[list[str]] = Field(
        None,
        description="AI-suggested trading actions",
        example=["Consider long USD positions", "Monitor EUR/USD closely"]
    )
    related_symbols: Optional[list[str]] = Field(
        None,
        description="Trading symbols related to this signal",
        example=["EUR/USD", "GBP/USD", "USD/JPY"]
    )
    confidence: Optional[float] = Field(
        None,
        description="AI confidence score (0-1)",
        ge=0,
        le=1,
        example=0.92
    )
    created_at: str = Field(
        ...,
        description="Signal creation timestamp (ISO 8601)",
        example="2024-01-15T10:30:00Z"
    )

class TradeResponse(BaseModel):
    """Trade response schema."""
    
    id: str = Field(
        ...,
        description="Trade UUID",
        example="550e8400-e29b-41d4-a716-446655440000"
    )
    order_id: Optional[str] = Field(
        None,
        description="Broker order ID",
        example="ORD-12345"
    )
    symbol: str = Field(
        ...,
        description="Trading symbol",
        example="EUR/USD"
    )
    direction: str = Field(
        ...,
        description="Trade direction",
        pattern="^(long|short)$",
        example="long"
    )
    volume: float = Field(
        ...,
        description="Trade volume (lots)",
        gt=0,
        example=0.1
    )
    entry_price: Optional[float] = Field(
        None,
        description="Entry price",
        example=1.0850
    )
    exit_price: Optional[float] = Field(
        None,
        description="Exit price",
        example=1.0920
    )
    stop_loss: Optional[float] = Field(
        None,
        description="Stop loss price",
        example=1.0800
    )
    take_profit: Optional[float] = Field(
        None,
        description="Take profit price",
        example=1.0950
    )
    profit: Optional[float] = Field(
        None,
        description="Realized profit/loss",
        example=70.0
    )
    status: str = Field(
        ...,
        description="Trade status",
        pattern="^(open|closed|cancelled)$",
        example="closed"
    )
    created_at: str = Field(
        ...,
        description="Trade creation timestamp (ISO 8601)",
        example="2024-01-15T10:30:00Z"
    )
    closed_at: Optional[str] = Field(
        None,
        description="Trade close timestamp (ISO 8601)",
        example="2024-01-15T12:45:00Z"
    )
    ea_profile_id: Optional[str] = Field(
        None,
        description="EA Profile UUID that generated this trade",
        example="550e8400-e29b-41d4-a716-446655440001"
    )

class ConfigResponse(BaseModel):
    """Configuration file response schema."""
    
    file_name: str = Field(
        ...,
        description="Configuration file name",
        example="fetch_sources.yaml"
    )
    content: str = Field(
        ...,
        description="Raw configuration file content",
        example="sources:\n  - source_id: bloomberg\n    enabled: true"
    )
    parsed: Optional[dict[str, Any]] = Field(
        None,
        description="Parsed YAML content (null if parsing failed)"
    )
    last_modified: str = Field(
        ...,
        description="Last modification timestamp (ISO 8601)",
        example="2024-01-15T10:30:00Z"
    )

class ConfigUpdateRequest(BaseModel):
    """Configuration update request schema."""
    
    content: str = Field(
        ...,
        description="New configuration file content (YAML format)",
        example="sources:\n  - source_id: bloomberg\n    enabled: true"
    )

class ConfigUpdateResponse(BaseModel):
    """Configuration update response schema."""
    
    success: bool = Field(
        ...,
        description="Whether the update was successful",
        example=True
    )
    message: str = Field(
        ...,
        description="Success or error message",
        example="Configuration 'fetch_sources.yaml' updated successfully"
    )
    file_name: str = Field(
        ...,
        description="Configuration file name",
        example="fetch_sources.yaml"
    )
    timestamp: str = Field(
        ...,
        description="Update timestamp (ISO 8601)",
        example="2024-01-15T10:30:00Z"
    )

class ErrorResponse(BaseModel):
    """Error response schema."""
    
    error: str = Field(
        ...,
        description="Error type/class name",
        example="ValidationError"
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        example="Invalid YAML syntax"
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error details"
    )
    timestamp: str = Field(
        ...,
        description="Error timestamp (ISO 8601)",
        example="2024-01-15T10:30:00Z"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid YAML syntax",
                "details": {
                    "line": 5,
                    "column": 12,
                    "problem": "expected <block end>, but found '-'"
                },
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
