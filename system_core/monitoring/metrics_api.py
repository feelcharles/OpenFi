"""
Metrics aggregation API for business intelligence.

Validates: Requirements 25.8
"""

from typing import Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .logger import get_logger
from .metrics import MetricsSummary
from system_core.database.models import Signal, Trade, Notification

logger = get_logger(__name__)

class MetricsAggregator:
    """
    Aggregates metrics from database for business intelligence.
    
    Validates: Requirements 25.8
    """
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize metrics aggregator.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
    
    def _get_time_range(self, period: str) -> tuple[datetime, datetime]:
        """
        Get time range for period.
        
        Args:
            period: Period string (1h, 24h, 7d, 30d)
            
        Returns:
            Tuple of (start_time, end_time)
        """
        end_time = datetime.utcnow()
        
        if period == "1h":
            start_time = end_time - timedelta(hours=1)
        elif period == "24h":
            start_time = end_time - timedelta(hours=24)
        elif period == "7d":
            start_time = end_time - timedelta(days=7)
        elif period == "30d":
            start_time = end_time - timedelta(days=30)
        else:
            raise ValueError(f"Invalid period: {period}. Must be one of: 1h, 24h, 7d, 30d")
        
        return start_time, end_time
    
    def get_signal_metrics(self, start_time: datetime, end_time: datetime) -> dict[str, Any]:
        """
        Get signal metrics for time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            Dict containing signal metrics
        """
        # Total signals
        total_signals = self.db.query(func.count(Signal.id)).filter(
            and_(
                Signal.created_at >= start_time,
                Signal.created_at <= end_time
            )
        ).scalar() or 0
        
        # High-value signals (relevance_score >= 70)
        high_value_signals = self.db.query(func.count(Signal.id)).filter(
            and_(
                Signal.created_at >= start_time,
                Signal.created_at <= end_time,
                Signal.relevance_score >= 70
            )
        ).scalar() or 0
        
        # Average relevance score
        avg_relevance = self.db.query(func.avg(Signal.relevance_score)).filter(
            and_(
                Signal.created_at >= start_time,
                Signal.created_at <= end_time
            )
        ).scalar() or 0.0
        
        # Signals by source type
        signals_by_source = {}
        source_counts = self.db.query(
            Signal.source_type,
            func.count(Signal.id)
        ).filter(
            and_(
                Signal.created_at >= start_time,
                Signal.created_at <= end_time
            )
        ).group_by(Signal.source_type).all()
        
        for source_type, count in source_counts:
            signals_by_source[source_type] = count
        
        # Signals by impact level
        signals_by_impact = {}
        impact_counts = self.db.query(
            Signal.potential_impact,
            func.count(Signal.id)
        ).filter(
            and_(
                Signal.created_at >= start_time,
                Signal.created_at <= end_time
            )
        ).group_by(Signal.potential_impact).all()
        
        for impact, count in impact_counts:
            signals_by_impact[impact] = count
        
        # Calculate rates
        high_value_rate = (high_value_signals / total_signals * 100) if total_signals > 0 else 0.0
        
        # Calculate signals per hour
        duration_hours = (end_time - start_time).total_seconds() / 3600
        signals_per_hour = total_signals / duration_hours if duration_hours > 0 else 0.0
        
        return {
            "total_signals": total_signals,
            "high_value_signals": high_value_signals,
            "high_value_rate": round(high_value_rate, 2),
            "average_relevance_score": round(float(avg_relevance), 2),
            "signals_per_hour": round(signals_per_hour, 2),
            "signals_by_source": signals_by_source,
            "signals_by_impact": signals_by_impact
        }
    
    def get_trade_metrics(self, start_time: datetime, end_time: datetime) -> dict[str, Any]:
        """
        Get trade metrics for time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            Dict containing trade metrics
        """
        # Total trades
        total_trades = self.db.query(func.count(Trade.id)).filter(
            and_(
                Trade.execution_time >= start_time,
                Trade.execution_time <= end_time
            )
        ).scalar() or 0
        
        # Winning trades (profit > 0)
        winning_trades = self.db.query(func.count(Trade.id)).filter(
            and_(
                Trade.execution_time >= start_time,
                Trade.execution_time <= end_time,
                Trade.profit > 0
            )
        ).scalar() or 0
        
        # Total profit
        total_profit = self.db.query(func.sum(Trade.profit)).filter(
            and_(
                Trade.execution_time >= start_time,
                Trade.execution_time <= end_time
            )
        ).scalar() or 0.0
        
        # Average profit per trade
        avg_profit = total_profit / total_trades if total_trades > 0 else 0.0
        
        # Win rate
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        # Trades by symbol
        trades_by_symbol = {}
        symbol_counts = self.db.query(
            Trade.symbol,
            func.count(Trade.id)
        ).filter(
            and_(
                Trade.execution_time >= start_time,
                Trade.execution_time <= end_time
            )
        ).group_by(Trade.symbol).all()
        
        for symbol, count in symbol_counts:
            trades_by_symbol[symbol] = count
        
        # Trades by direction
        trades_by_direction = {}
        direction_counts = self.db.query(
            Trade.direction,
            func.count(Trade.id)
        ).filter(
            and_(
                Trade.execution_time >= start_time,
                Trade.execution_time <= end_time
            )
        ).group_by(Trade.direction).all()
        
        for direction, count in direction_counts:
            trades_by_direction[direction] = count
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "win_rate": round(win_rate, 2),
            "total_profit": round(float(total_profit), 2),
            "average_profit_per_trade": round(avg_profit, 2),
            "trades_by_symbol": trades_by_symbol,
            "trades_by_direction": trades_by_direction
        }
    
    def get_notification_metrics(self, start_time: datetime, end_time: datetime) -> dict[str, Any]:
        """
        Get notification metrics for time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            
        Returns:
            Dict containing notification metrics
        """
        # Total notifications
        total_notifications = self.db.query(func.count(Notification.id)).filter(
            and_(
                Notification.created_at >= start_time,
                Notification.created_at <= end_time
            )
        ).scalar() or 0
        
        # Successful notifications
        successful_notifications = self.db.query(func.count(Notification.id)).filter(
            and_(
                Notification.created_at >= start_time,
                Notification.created_at <= end_time,
                Notification.status == "sent"
            )
        ).scalar() or 0
        
        # Failed notifications
        failed_notifications = self.db.query(func.count(Notification.id)).filter(
            and_(
                Notification.created_at >= start_time,
                Notification.created_at <= end_time,
                Notification.status == "failed"
            )
        ).scalar() or 0
        
        # Success rate
        success_rate = (successful_notifications / total_notifications * 100) if total_notifications > 0 else 0.0
        
        # Notifications by channel
        notifications_by_channel = {}
        channel_counts = self.db.query(
            Notification.channel,
            func.count(Notification.id)
        ).filter(
            and_(
                Notification.created_at >= start_time,
                Notification.created_at <= end_time
            )
        ).group_by(Notification.channel).all()
        
        for channel, count in channel_counts:
            notifications_by_channel[channel] = count
        
        return {
            "total_notifications": total_notifications,
            "successful_notifications": successful_notifications,
            "failed_notifications": failed_notifications,
            "success_rate": round(success_rate, 2),
            "notifications_by_channel": notifications_by_channel
        }
    
    async def get_summary(self, period: str = "24h") -> MetricsSummary:
        """
        Get comprehensive metrics summary for period.
        
        Args:
            period: Time period (1h, 24h, 7d, 30d)
            
        Returns:
            MetricsSummary: Aggregated metrics summary
            
        Validates: Requirements 25.8
        """
        start_time, end_time = self._get_time_range(period)
        
        logger.info(
            "metrics_aggregation_started",
            period=period,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat()
        )
        
        # Gather all metrics
        signal_metrics = self.get_signal_metrics(start_time, end_time)
        trade_metrics = self.get_trade_metrics(start_time, end_time)
        notification_metrics = self.get_notification_metrics(start_time, end_time)
        
        # Build summary
        summary = MetricsSummary(
            period=period,
            start_time=start_time,
            end_time=end_time,
            metrics={
                "signals": signal_metrics,
                "trades": trade_metrics,
                "notifications": notification_metrics
            }
        )
        
        logger.info(
            "metrics_aggregation_completed",
            period=period,
            total_signals=signal_metrics["total_signals"],
            total_trades=trade_metrics["total_trades"],
            total_notifications=notification_metrics["total_notifications"]
        )
        
        return summary

