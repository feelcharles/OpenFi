"""
Prometheus metrics collection and exposure.

Validates: Requirements 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7, 25.8
"""

from typing import Optional, Any
from datetime import datetime, timedelta
from prometheus_client import (
    Counter, Gauge, Histogram, Summary, Info,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)
from dataclasses import dataclass, field

from .logger import get_logger

logger = get_logger(__name__)

@dataclass
class MetricsSummary:
    """Summary of metrics for a time period."""
    period: str
    start_time: datetime
    end_time: datetime
    metrics: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "period": self.period,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "metrics": self.metrics
        }

class MetricsCollector:
    """
    Centralized metrics collector using Prometheus client.
    
    Validates: Requirements 25.1, 25.2, 25.3, 25.4, 25.5, 25.6, 25.7
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector.
        
        Args:
            registry: Prometheus registry (uses default if None)
        """
        self.registry = registry or CollectorRegistry()
        
        # Counter metrics (Requirements 25.2)
        self.total_fetch_requests = Counter(
            'total_fetch_requests',
            'Total number of fetch requests',
            ['source_type', 'status'],
            registry=self.registry
        )
        
        self.total_llm_calls = Counter(
            'total_llm_calls',
            'Total number of LLM API calls',
            ['provider', 'model', 'status'],
            registry=self.registry
        )
        
        self.total_trades_executed = Counter(
            'total_trades_executed',
            'Total number of trades executed',
            ['symbol', 'direction', 'status'],
            registry=self.registry
        )
        
        self.total_notifications_sent = Counter(
            'total_notifications_sent',
            'Total number of notifications sent',
            ['channel', 'status'],
            registry=self.registry
        )
        
        # Gauge metrics (Requirements 25.3)
        self.active_fetch_tasks = Gauge(
            'active_fetch_tasks',
            'Number of active fetch tasks',
            ['source_type'],
            registry=self.registry
        )
        
        self.event_bus_queue_depth = Gauge(
            'event_bus_queue_depth',
            'Depth of event bus queue',
            ['topic'],
            registry=self.registry
        )
        
        self.active_positions = Gauge(
            'active_positions',
            'Number of active trading positions',
            ['symbol', 'direction'],
            registry=self.registry
        )
        
        self.account_balance = Gauge(
            'account_balance',
            'Current account balance',
            ['account_id', 'currency'],
            registry=self.registry
        )
        
        # Histogram metrics (Requirements 25.4)
        self.fetch_duration_seconds = Histogram(
            'fetch_duration_seconds',
            'Duration of fetch operations in seconds',
            ['source_type'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry
        )
        
        self.llm_response_time_seconds = Histogram(
            'llm_response_time_seconds',
            'LLM response time in seconds',
            ['provider', 'model'],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0],
            registry=self.registry
        )
        
        self.trade_execution_time_seconds = Histogram(
            'trade_execution_time_seconds',
            'Trade execution time in seconds',
            ['broker', 'order_type'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
            registry=self.registry
        )
        
        self.notification_delivery_time_seconds = Histogram(
            'notification_delivery_time_seconds',
            'Notification delivery time in seconds',
            ['channel'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        # Summary metrics (Requirements 25.5)
        self.data_quality_scores = Summary(
            'data_quality_scores',
            'Data quality scores',
            ['source_type', 'data_type'],
            registry=self.registry
        )
        
        self.relevance_scores = Summary(
            'relevance_scores',
            'AI relevance scores',
            ['data_type'],
            registry=self.registry
        )
        
        self.position_sizes = Summary(
            'position_sizes',
            'Trading position sizes',
            ['symbol', 'ea_name'],
            registry=self.registry
        )
        
        # Business KPI metrics (Requirements 25.7)
        self.signals_per_hour = Gauge(
            'signals_per_hour',
            'Number of signals generated per hour',
            registry=self.registry
        )
        
        self.high_value_signal_rate = Gauge(
            'high_value_signal_rate',
            'Percentage of high-value signals',
            registry=self.registry
        )
        
        self.trade_win_rate = Gauge(
            'trade_win_rate',
            'Percentage of winning trades',
            ['ea_name'],
            registry=self.registry
        )
        
        self.average_profit_per_trade = Gauge(
            'average_profit_per_trade',
            'Average profit per trade',
            ['ea_name', 'symbol'],
            registry=self.registry
        )
        
        logger.info("metrics_collector_initialized")
    
    # Counter methods
    def increment_fetch_requests(self, source_type: str, status: str = "success") -> None:
        """Increment fetch requests counter."""
        self.total_fetch_requests.labels(source_type=source_type, status=status).inc()
    
    def increment_llm_calls(self, provider: str, model: str, status: str = "success") -> None:
        """Increment LLM calls counter."""
        self.total_llm_calls.labels(provider=provider, model=model, status=status).inc()
    
    def increment_trades_executed(self, symbol: str, direction: str, status: str = "success") -> None:
        """Increment trades executed counter."""
        self.total_trades_executed.labels(symbol=symbol, direction=direction, status=status).inc()
    
    def increment_notifications_sent(self, channel: str, status: str = "success") -> None:
        """Increment notifications sent counter."""
        self.total_notifications_sent.labels(channel=channel, status=status).inc()
    
    # Gauge methods
    def set_active_fetch_tasks(self, source_type: str, count: int) -> None:
        """Set active fetch tasks gauge."""
        self.active_fetch_tasks.labels(source_type=source_type).set(count)
    
    def set_event_bus_queue_depth(self, topic: str, depth: int) -> None:
        """Set event bus queue depth gauge."""
        self.event_bus_queue_depth.labels(topic=topic).set(depth)
    
    def set_active_positions(self, symbol: str, direction: str, count: int) -> None:
        """Set active positions gauge."""
        self.active_positions.labels(symbol=symbol, direction=direction).set(count)
    
    def set_account_balance(self, account_id: str, currency: str, balance: float) -> None:
        """Set account balance gauge."""
        self.account_balance.labels(account_id=account_id, currency=currency).set(balance)
    
    # Histogram methods
    def observe_fetch_duration(self, source_type: str, duration: float) -> None:
        """Observe fetch duration."""
        self.fetch_duration_seconds.labels(source_type=source_type).observe(duration)
    
    def observe_llm_response_time(self, provider: str, model: str, duration: float) -> None:
        """Observe LLM response time."""
        self.llm_response_time_seconds.labels(provider=provider, model=model).observe(duration)
    
    def observe_trade_execution_time(self, broker: str, order_type: str, duration: float) -> None:
        """Observe trade execution time."""
        self.trade_execution_time_seconds.labels(broker=broker, order_type=order_type).observe(duration)
    
    def observe_notification_delivery_time(self, channel: str, duration: float) -> None:
        """Observe notification delivery time."""
        self.notification_delivery_time_seconds.labels(channel=channel).observe(duration)
    
    # Summary methods
    def observe_data_quality_score(self, source_type: str, data_type: str, score: float) -> None:
        """Observe data quality score."""
        self.data_quality_scores.labels(source_type=source_type, data_type=data_type).observe(score)
    
    def observe_relevance_score(self, data_type: str, score: float) -> None:
        """Observe relevance score."""
        self.relevance_scores.labels(data_type=data_type).observe(score)
    
    def observe_position_size(self, symbol: str, ea_name: str, size: float) -> None:
        """Observe position size."""
        self.position_sizes.labels(symbol=symbol, ea_name=ea_name).observe(size)
    
    # Business KPI methods
    def set_signals_per_hour(self, count: float) -> None:
        """Set signals per hour."""
        self.signals_per_hour.set(count)
    
    def set_high_value_signal_rate(self, rate: float) -> None:
        """Set high-value signal rate (0-100)."""
        self.high_value_signal_rate.set(rate)
    
    def set_trade_win_rate(self, ea_name: str, rate: float) -> None:
        """Set trade win rate (0-100)."""
        self.trade_win_rate.labels(ea_name=ea_name).set(rate)
    
    def set_average_profit_per_trade(self, ea_name: str, symbol: str, profit: float) -> None:
        """Set average profit per trade."""
        self.average_profit_per_trade.labels(ea_name=ea_name, symbol=symbol).set(profit)
    
    def record_metric(self, metric_name: str, value: float, labels: dict = None) -> None:
        """
        Generic method to record a metric (for backward compatibility).
        
        This method attempts to find an appropriate metric to record the value.
        
        Args:
            metric_name: Name of the metric
            value: Value to record
            labels: Optional labels dictionary
        """
        # Map common metric names to specific methods
        if metric_name == "fetch_requests":
            self.increment_fetch_requests(
                source_type=labels.get("source_type", "unknown") if labels else "unknown",
                status=labels.get("status", "success") if labels else "success"
            )
        elif metric_name == "llm_calls":
            self.increment_llm_calls(
                provider=labels.get("provider", "unknown") if labels else "unknown",
                model=labels.get("model", "unknown") if labels else "unknown",
                status=labels.get("status", "success") if labels else "success"
            )
        elif metric_name == "signals_per_hour":
            self.set_signals_per_hour(value)
        elif metric_name == "high_value_signal_rate":
            self.set_high_value_signal_rate(value)
        else:
            # For unknown metrics, just log
            logger.debug(f"Recorded generic metric: {metric_name}={value}, labels={labels}")
    
    def get_metrics_text(self) -> bytes:
        """
        Get metrics in Prometheus text format.
        
        Returns:
            bytes: Metrics in Prometheus exposition format
            
        Validates: Requirements 25.1
        """
        return generate_latest(self.registry)
    
    def get_content_type(self) -> str:
        """
        Get content type for metrics endpoint.
        
        Returns:
            str: Content type header value
        """
        return CONTENT_TYPE_LATEST

# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None

def get_metrics_collector() -> MetricsCollector:
    """
    Get global metrics collector instance.
    
    Returns:
        MetricsCollector: Global metrics collector
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

def reset_metrics_collector() -> None:
    """Reset global metrics collector (useful for testing)."""
    global _metrics_collector
    _metrics_collector = None
