"""
Alerting system integration with webhook notifications.

Validates: Requirements 36.3, 36.4, 36.5, 36.6, 36.8
"""

from typing import Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import aiohttp
from dataclasses import dataclass, field
from collections import defaultdict

from .logger import get_logger
from ..database.client import get_session
from ..database.models import AlertLog

logger = get_logger(__name__)

class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class AlertCondition(str, Enum):
    """Alert condition types."""
    HIGH_ERROR_RATE = "high_error_rate"
    LOW_SUCCESS_RATE = "low_success_rate"
    HIGH_LATENCY = "high_latency"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    QUEUE_DEPTH_EXCEEDED = "queue_depth_exceeded"
    SERVICE_DOWN = "service_down"

@dataclass
class Alert:
    """Alert data structure."""
    condition: AlertCondition
    severity: AlertSeverity
    component: str
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)
    runbook_url: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "condition": self.condition.value,
            "severity": self.severity.value,
            "component": self.component,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "runbook_url": self.runbook_url
        }

class AlertDeduplicator:
    """
    Alert deduplication to prevent alert storms.
    
    Validates: Requirement 36.6
    """
    
    def __init__(self, window_seconds: int = 300):
        """
        Initialize deduplicator.
        
        Args:
            window_seconds: Deduplication window (default 5 minutes)
        """
        self.window_seconds = window_seconds
        self._alert_history: dict[str, datetime] = {}
        self._lock = asyncio.Lock()
    
    def _get_alert_key(self, alert: Alert) -> str:
        """Generate unique key for alert."""
        return f"{alert.condition.value}:{alert.component}"
    
    async def should_send_alert(self, alert: Alert) -> bool:
        """
        Check if alert should be sent based on deduplication rules.
        
        Args:
            alert: Alert to check
            
        Returns:
            bool: True if alert should be sent, False if deduplicated
            
        Validates: Requirement 36.6 (max 1 alert per condition per 5 minutes)
        """
        async with self._lock:
            alert_key = self._get_alert_key(alert)
            now = datetime.utcnow()
            
            # Check if we've sent this alert recently
            if alert_key in self._alert_history:
                last_sent = self._alert_history[alert_key]
                time_since_last = (now - last_sent).total_seconds()
                
                if time_since_last < self.window_seconds:
                    logger.debug(
                        "alert_deduplicated",
                        alert_key=alert_key,
                        time_since_last=time_since_last,
                        window_seconds=self.window_seconds
                    )
                    return False
            
            # Update history and allow alert
            self._alert_history[alert_key] = now
            
            # Clean up old entries
            cutoff_time = now - timedelta(seconds=self.window_seconds * 2)
            self._alert_history = {
                k: v for k, v in self._alert_history.items()
                if v > cutoff_time
            }
            
            return True

class WebhookNotifier:
    """Base class for webhook notifications."""
    
    def __init__(self, webhook_url: str, timeout: int = 10):
        """
        Initialize webhook notifier.
        
        Args:
            webhook_url: Webhook URL
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.timeout = timeout
    
    async def send(self, alert: Alert) -> bool:
        """
        Send alert via webhook.
        
        Args:
            alert: Alert to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            payload = self._format_payload(alert)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status in (200, 201, 202, 204):
                        logger.info(
                            "alert_sent_successfully",
                            notifier=self.__class__.__name__,
                            condition=alert.condition.value,
                            component=alert.component
                        )
                        return True
                    else:
                        logger.error(
                            "alert_send_failed",
                            notifier=self.__class__.__name__,
                            status=response.status,
                            response=await response.text()
                        )
                        return False
        except Exception as e:
            logger.error(
                "alert_send_exception",
                notifier=self.__class__.__name__,
                error=str(e),
                alert=alert.to_dict()
            )
            return False
    
    def _format_payload(self, alert: Alert) -> dict[str, Any]:
        """Format alert payload for webhook. Override in subclasses."""
        raise NotImplementedError

class PagerDutyNotifier(WebhookNotifier):
    """
    PagerDuty webhook notifier.
    
    Validates: Requirement 36.3
    """
    
    def __init__(self, integration_key: str, webhook_url: Optional[str] = None):
        """
        Initialize PagerDuty notifier.
        
        Args:
            integration_key: PagerDuty integration key
            webhook_url: Optional custom webhook URL
        """
        self.integration_key = integration_key
        url = webhook_url or "https://events.pagerduty.com/v2/enqueue"
        super().__init__(url)
    
    def _format_payload(self, alert: Alert) -> dict[str, Any]:
        """Format alert for PagerDuty Events API v2."""
        severity_map = {
            AlertSeverity.CRITICAL: "critical",
            AlertSeverity.ERROR: "error",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.INFO: "info"
        }
        
        return {
            "routing_key": self.integration_key,
            "event_action": "trigger",
            "payload": {
                "summary": f"[{alert.component}] {alert.message}",
                "severity": severity_map.get(alert.severity, "error"),
                "source": alert.component,
                "timestamp": alert.timestamp.isoformat(),
                "custom_details": {
                    "condition": alert.condition.value,
                    "metadata": alert.metadata,
                    "runbook_url": alert.runbook_url
                }
            },
            "links": [
                {
                    "href": alert.runbook_url,
                    "text": "Runbook"
                }
            ] if alert.runbook_url else []
        }

class OpsgenieNotifier(WebhookNotifier):
    """
    Opsgenie webhook notifier.
    
    Validates: Requirement 36.3
    """
    
    def __init__(self, api_key: str, webhook_url: Optional[str] = None):
        """
        Initialize Opsgenie notifier.
        
        Args:
            api_key: Opsgenie API key
            webhook_url: Optional custom webhook URL
        """
        self.api_key = api_key
        url = webhook_url or "https://api.opsgenie.com/v2/alerts"
        super().__init__(url)
    
    def _format_payload(self, alert: Alert) -> dict[str, Any]:
        """Format alert for Opsgenie API."""
        priority_map = {
            AlertSeverity.CRITICAL: "P1",
            AlertSeverity.ERROR: "P2",
            AlertSeverity.WARNING: "P3",
            AlertSeverity.INFO: "P5"
        }
        
        return {
            "message": f"[{alert.component}] {alert.message}",
            "description": f"Condition: {alert.condition.value}\n\nMetadata: {alert.metadata}",
            "priority": priority_map.get(alert.severity, "P3"),
            "source": alert.component,
            "tags": [alert.condition.value, alert.component],
            "details": {
                "condition": alert.condition.value,
                "severity": alert.severity.value,
                "timestamp": alert.timestamp.isoformat(),
                "metadata": alert.metadata,
                "runbook_url": alert.runbook_url
            }
        }
    
    async def send(self, alert: Alert) -> bool:
        """Send alert with API key header."""
        try:
            payload = self._format_payload(alert)
            headers = {"Authorization": f"GenieKey {self.api_key}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status in (200, 201, 202):
                        logger.info(
                            "alert_sent_successfully",
                            notifier=self.__class__.__name__,
                            condition=alert.condition.value,
                            component=alert.component
                        )
                        return True
                    else:
                        logger.error(
                            "alert_send_failed",
                            notifier=self.__class__.__name__,
                            status=response.status,
                            response=await response.text()
                        )
                        return False
        except Exception as e:
            logger.error(
                "alert_send_exception",
                notifier=self.__class__.__name__,
                error=str(e),
                alert=alert.to_dict()
            )
            return False

class SlackNotifier(WebhookNotifier):
    """
    Slack webhook notifier.
    
    Validates: Requirement 36.3
    """
    
    def _format_payload(self, alert: Alert) -> dict[str, Any]:
        """Format alert for Slack webhook."""
        color_map = {
            AlertSeverity.CRITICAL: "#FF0000",
            AlertSeverity.ERROR: "#FF6B6B",
            AlertSeverity.WARNING: "#FFA500",
            AlertSeverity.INFO: "#36A64F"
        }
        
        emoji_map = {
            AlertSeverity.CRITICAL: ":rotating_light:",
            AlertSeverity.ERROR: ":x:",
            AlertSeverity.WARNING: ":warning:",
            AlertSeverity.INFO: ":information_source:"
        }
        
        fields = [
            {
                "title": "Component",
                "value": alert.component,
                "short": True
            },
            {
                "title": "Condition",
                "value": alert.condition.value,
                "short": True
            },
            {
                "title": "Severity",
                "value": alert.severity.value.upper(),
                "short": True
            },
            {
                "title": "Timestamp",
                "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "short": True
            }
        ]
        
        # Add metadata fields
        for key, value in alert.metadata.items():
            fields.append({
                "title": key.replace("_", " ").title(),
                "value": str(value),
                "short": True
            })
        
        attachment = {
            "color": color_map.get(alert.severity, "#808080"),
            "title": f"{emoji_map.get(alert.severity, '')} {alert.message}",
            "fields": fields,
            "footer": "OpenFi Lite Monitoring",
            "ts": int(alert.timestamp.timestamp())
        }
        
        if alert.runbook_url:
            attachment["actions"] = [
                {
                    "type": "button",
                    "text": "View Runbook",
                    "url": alert.runbook_url
                }
            ]
        
        return {
            "attachments": [attachment]
        }

class AlertManager:
    """
    Central alert management system.
    
    Validates: Requirements 36.3, 36.4, 36.5, 36.6, 36.8
    """
    
    def __init__(
        self,
        pagerduty_key: Optional[str] = None,
        opsgenie_key: Optional[str] = None,
        slack_webhook: Optional[str] = None,
        deduplication_window: int = 300
    ):
        """
        Initialize alert manager.
        
        Args:
            pagerduty_key: PagerDuty integration key
            opsgenie_key: Opsgenie API key
            slack_webhook: Slack webhook URL
            deduplication_window: Deduplication window in seconds (default 5 minutes)
        """
        self.notifiers: list[WebhookNotifier] = []
        
        if pagerduty_key:
            self.notifiers.append(PagerDutyNotifier(pagerduty_key))
        
        if opsgenie_key:
            self.notifiers.append(OpsgenieNotifier(opsgenie_key))
        
        if slack_webhook:
            self.notifiers.append(SlackNotifier(slack_webhook))
        
        self.deduplicator = AlertDeduplicator(window_seconds=deduplication_window)
        
        # Runbook URLs for different conditions
        self.runbook_urls = {
            AlertCondition.HIGH_ERROR_RATE: "https://docs.OpenFi.io/runbooks/high-error-rate",
            AlertCondition.LOW_SUCCESS_RATE: "https://docs.OpenFi.io/runbooks/low-success-rate",
            AlertCondition.HIGH_LATENCY: "https://docs.OpenFi.io/runbooks/high-latency",
            AlertCondition.CIRCUIT_BREAKER_TRIGGERED: "https://docs.OpenFi.io/runbooks/circuit-breaker",
            AlertCondition.QUEUE_DEPTH_EXCEEDED: "https://docs.OpenFi.io/runbooks/queue-depth",
            AlertCondition.SERVICE_DOWN: "https://docs.OpenFi.io/runbooks/service-down"
        }
        
        logger.info(
            "alert_manager_initialized",
            notifier_count=len(self.notifiers),
            deduplication_window=deduplication_window
        )
    
    async def send_alert(self, alert: Alert) -> bool:
        """
        Send alert through all configured notifiers.
        
        Args:
            alert: Alert to send
            
        Returns:
            bool: True if at least one notifier succeeded
            
        Validates: Requirements 36.3, 36.5, 36.6
        """
        # Add runbook URL if not provided
        if not alert.runbook_url and alert.condition in self.runbook_urls:
            alert.runbook_url = self.runbook_urls[alert.condition]
        
        # Check deduplication
        if not await self.deduplicator.should_send_alert(alert):
            logger.info(
                "alert_deduplicated",
                condition=alert.condition.value,
                component=alert.component
            )
            return False
        
        # Log alert to database (Requirement 36.8)
        await self._log_alert_to_database(alert)
        
        # Send to all notifiers
        if not self.notifiers:
            logger.warning("no_notifiers_configured")
            return False
        
        results = await asyncio.gather(
            *[notifier.send(alert) for notifier in self.notifiers],
            return_exceptions=True
        )
        
        success_count = sum(1 for r in results if r is True)
        
        logger.info(
            "alert_sent",
            condition=alert.condition.value,
            component=alert.component,
            severity=alert.severity.value,
            success_count=success_count,
            total_notifiers=len(self.notifiers)
        )
        
        return success_count > 0
    
    async def _log_alert_to_database(self, alert: Alert) -> None:
        """
        Log alert to database for historical analysis.
        
        Validates: Requirement 36.8
        """
        try:
            async with get_session() as session:
                alert_log = AlertLog(
                    condition=alert.condition.value,
                    severity=alert.severity.value,
                    component=alert.component,
                    message=alert.message,
                    metadata=alert.metadata,
                    runbook_url=alert.runbook_url,
                    timestamp=alert.timestamp
                )
                session.add(alert_log)
                await session.commit()
                
                logger.debug(
                    "alert_logged_to_database",
                    condition=alert.condition.value,
                    component=alert.component
                )
        except Exception as e:
            logger.error(
                "alert_database_logging_failed",
                error=str(e),
                alert=alert.to_dict()
            )
    
    async def check_high_error_rate(
        self,
        component: str,
        error_count: int,
        total_count: int,
        threshold: float = 0.05
    ) -> None:
        """
        Check for high error rate and send alert if threshold exceeded.
        
        Args:
            component: Component name
            error_count: Number of errors
            total_count: Total number of operations
            threshold: Error rate threshold (default 5%)
            
        Validates: Requirement 36.4
        """
        if total_count == 0:
            return
        
        error_rate = error_count / total_count
        
        if error_rate > threshold:
            alert = Alert(
                condition=AlertCondition.HIGH_ERROR_RATE,
                severity=AlertSeverity.ERROR,
                component=component,
                message=f"High error rate detected: {error_rate*100:.2f}%",
                metadata={
                    "error_count": error_count,
                    "total_count": total_count,
                    "error_rate": f"{error_rate*100:.2f}%",
                    "threshold": f"{threshold*100:.2f}%"
                }
            )
            await self.send_alert(alert)
    
    async def check_low_success_rate(
        self,
        component: str,
        success_count: int,
        total_count: int,
        threshold: float = 0.90
    ) -> None:
        """
        Check for low success rate and send alert if below threshold.
        
        Args:
            component: Component name
            success_count: Number of successes
            total_count: Total number of operations
            threshold: Success rate threshold (default 90%)
            
        Validates: Requirement 36.4
        """
        if total_count == 0:
            return
        
        success_rate = success_count / total_count
        
        if success_rate < threshold:
            alert = Alert(
                condition=AlertCondition.LOW_SUCCESS_RATE,
                severity=AlertSeverity.WARNING,
                component=component,
                message=f"Low success rate detected: {success_rate*100:.2f}%",
                metadata={
                    "success_count": success_count,
                    "total_count": total_count,
                    "success_rate": f"{success_rate*100:.2f}%",
                    "threshold": f"{threshold*100:.2f}%"
                }
            )
            await self.send_alert(alert)
    
    async def check_high_latency(
        self,
        component: str,
        latency_seconds: float,
        threshold: float = 5.0
    ) -> None:
        """
        Check for high latency and send alert if threshold exceeded.
        
        Args:
            component: Component name
            latency_seconds: Latency in seconds
            threshold: Latency threshold in seconds (default 5s)
            
        Validates: Requirement 36.4
        """
        if latency_seconds > threshold:
            alert = Alert(
                condition=AlertCondition.HIGH_LATENCY,
                severity=AlertSeverity.WARNING,
                component=component,
                message=f"High latency detected: {latency_seconds:.2f}s",
                metadata={
                    "latency_seconds": latency_seconds,
                    "threshold_seconds": threshold
                }
            )
            await self.send_alert(alert)
    
    async def alert_circuit_breaker_triggered(
        self,
        component: str,
        ea_name: str,
        reason: str,
        metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Send alert when circuit breaker is triggered.
        
        Args:
            component: Component name
            ea_name: EA name
            reason: Reason for circuit breaker trigger
            metadata: Additional metadata
            
        Validates: Requirement 36.4
        """
        alert = Alert(
            condition=AlertCondition.CIRCUIT_BREAKER_TRIGGERED,
            severity=AlertSeverity.CRITICAL,
            component=component,
            message=f"Circuit breaker triggered for EA: {ea_name}",
            metadata={
                "ea_name": ea_name,
                "reason": reason,
                **(metadata or {})
            }
        )
        await self.send_alert(alert)

# Global alert manager instance
_alert_manager: Optional[AlertManager] = None

def get_alert_manager() -> AlertManager:
    """Get global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        raise RuntimeError("Alert manager not initialized. Call initialize_alert_manager() first.")
    return _alert_manager

def initialize_alert_manager(
    pagerduty_key: Optional[str] = None,
    opsgenie_key: Optional[str] = None,
    slack_webhook: Optional[str] = None,
    deduplication_window: int = 300
) -> AlertManager:
    """
    Initialize global alert manager.
    
    Args:
        pagerduty_key: PagerDuty integration key
        opsgenie_key: Opsgenie API key
        slack_webhook: Slack webhook URL
        deduplication_window: Deduplication window in seconds
        
    Returns:
        AlertManager: Initialized alert manager
    """
    global _alert_manager
    _alert_manager = AlertManager(
        pagerduty_key=pagerduty_key,
        opsgenie_key=opsgenie_key,
        slack_webhook=slack_webhook,
        deduplication_window=deduplication_window
    )
    return _alert_manager
