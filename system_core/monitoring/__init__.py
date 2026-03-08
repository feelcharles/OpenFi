"""
Monitoring and observability module.

This module provides comprehensive monitoring capabilities including:
- Structured logging with trace_id propagation
- Prometheus metrics collection and exposure
- Health check endpoints
- Error recovery strategies
- Metrics aggregation for business intelligence
"""

from .logger import (
    get_logger,
    setup_logging_with_trace_id,
    get_trace_id,
    set_trace_id,
    clear_trace_id,
    log_exception
)
from .metrics import MetricsCollector, get_metrics_collector, reset_metrics_collector
from .health import HealthChecker, ComponentStatus, get_health_checker, register_health_check
from .error_recovery import (
    retry_with_backoff,
    with_retry,
    FallbackHandler,
    SimpleCircuitBreaker,
    RetryExhaustedError,
    CircuitBreakerOpenError
)
from .metrics_api import MetricsAggregator, MetricsSummary
from .alerting import (
    Alert,
    AlertSeverity,
    AlertCondition,
    AlertManager,
    get_alert_manager,
    initialize_alert_manager,
    PagerDutyNotifier,
    OpsgenieNotifier,
    SlackNotifier
)
from .enhanced_health import (
    EnhancedHealthChecker,
    DetailedComponentStatus,
    get_enhanced_health_checker
)

__all__ = [
    # Logger
    "get_logger",
    "setup_logging_with_trace_id",
    "get_trace_id",
    "set_trace_id",
    "clear_trace_id",
    "log_exception",
    # Metrics
    "MetricsCollector",
    "get_metrics_collector",
    "reset_metrics_collector",
    "MetricsAggregator",
    "MetricsSummary",
    # Health
    "HealthChecker",
    "ComponentStatus",
    "get_health_checker",
    "register_health_check",
    "EnhancedHealthChecker",
    "DetailedComponentStatus",
    "get_enhanced_health_checker",
    # Error Recovery
    "retry_with_backoff",
    "with_retry",
    "FallbackHandler",
    "SimpleCircuitBreaker",
    "RetryExhaustedError",
    "CircuitBreakerOpenError",
    # Alerting
    "Alert",
    "AlertSeverity",
    "AlertCondition",
    "AlertManager",
    "get_alert_manager",
    "initialize_alert_manager",
    "PagerDutyNotifier",
    "OpsgenieNotifier",
    "SlackNotifier",
]
