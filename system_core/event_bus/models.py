"""
Event Bus Data Models

Defines the standard event format and related models.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

class Event(BaseModel):
    """
    Standard event format for Event Bus.
    
    All events published through the Event Bus follow this schema.
    """
    
    event_id: UUID = Field(description="Unique event identifier")
    event_type: str = Field(description="Event type (e.g., 'data.raw', 'ai.analyzed')")
    topic: str = Field(description="Topic name where event was published")
    payload: dict[str, Any] = Field(description="Event payload data")
    timestamp: datetime = Field(description="Event creation timestamp (UTC)")
    schema_version: str = Field(default="1.0", description="Event schema version")
    trace_id: UUID = Field(description="Trace ID for distributed tracing")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }

class RawDataEvent(BaseModel):
    """Raw data event payload from fetch engine."""
    
    source: str = Field(description="Data source identifier")
    source_type: str = Field(description="Source type (economic_calendar, market_data, etc.)")
    data_type: str = Field(description="Data type (economic_event, news, etc.)")
    timestamp: datetime = Field(description="Data timestamp")
    content: dict[str, Any] = Field(description="Raw data content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    quality_score: float = Field(default=0.0, description="Data quality score (0-100)")
    fetch_time: datetime = Field(description="Time when data was fetched")

class HighValueSignalEvent(BaseModel):
    """High-value signal event payload from AI processing engine."""
    
    signal_id: UUID = Field(description="Signal identifier")
    source: str = Field(description="Original data source")
    relevance_score: int = Field(ge=0, le=100, description="Relevance score (0-100)")
    potential_impact: str = Field(description="Potential impact (low/medium/high)")
    summary: str = Field(description="Signal summary")
    suggested_actions: list[str] = Field(default_factory=list, description="Suggested actions")
    related_symbols: list[str] = Field(default_factory=list, description="Related trading symbols")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    reasoning: str = Field(description="Analysis reasoning")

class TradingSignalEvent(BaseModel):
    """Trading signal event payload from execution engine."""
    
    signal_id: UUID = Field(description="Signal identifier")
    ea_profile_id: UUID = Field(description="EA profile identifier")
    symbol: str = Field(description="Trading symbol")
    direction: str = Field(description="Trade direction (long/short)")
    volume: float = Field(gt=0, description="Trade volume")
    entry_price: float = Field(gt=0, description="Entry price")
    stop_loss: float = Field(gt=0, description="Stop loss price")
    take_profit: float = Field(gt=0, description="Take profit price")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence score")
    reasoning: str = Field(description="Signal reasoning")
    timestamp: datetime = Field(description="Signal generation timestamp")
