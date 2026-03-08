"""
Push Notification Manager

Manages multi-channel push notifications for high-value signals.
Subscribes to Event Bus, queries user channels, and delivers notifications.
"""

import asyncio
from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.config import get_logger
from system_core.config.push_config import PushConfigManager
from system_core.database.models import User, Notification, Signal
from system_core.event_bus.event_bus import EventBus
from system_core.event_bus.models import Event
from system_core.user_center.push_channels import (
    PushChannel,
    TelegramChannel,
    DiscordChannel,
    FeishuChannel,
    WeChatWorkChannel,
    EmailChannel
)
from system_core.user_center.alert_rule_engine import AlertRuleEngine
from system_core.user_center.bot_command_handler import BotCommandHandler

logger = get_logger(__name__)

class PushNotificationManager:
    """
    Manages multi-channel push notifications.
    
    Features:
    - Subscribes to Event Bus topic "ai.high_value_signal"
    - Queries user's enabled push channels from database
    - Formats and delivers notifications to all enabled channels
    - Implements retry logic with configurable attempts and delays
    - Tracks delivery metrics per channel
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        db_session_factory,
        config_path: str = "config/push_config.yaml"
    ):
        """
        Initialize Push Notification Manager.
        
        Args:
            event_bus: Event bus instance for subscribing to signals
            db_session_factory: Factory function to create database sessions
            config_path: Path to push configuration file
        """
        self.event_bus = event_bus
        self.db_session_factory = db_session_factory
        
        # Initialize alert rule engine
        self.alert_rule_engine = AlertRuleEngine(db_session_factory)
        
        # Initialize bot command handler
        self.bot_command_handler = BotCommandHandler()
        
        # Load push configuration
        self.config_manager = PushConfigManager(config_path)
        self.config_manager.load()
        # Get raw config dict for channel initialization
        import yaml
        from pathlib import Path
        with open(Path(config_path), 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize channel adapters
        self.channels: dict[str, PushChannel] = {}
        self._initialize_channels()
        
        # Metrics tracking
        self.metrics: dict[str, dict[str, int]] = {}
        self._initialize_metrics()
        
        # Subscription task
        self._subscription_task: Optional[asyncio.Task] = None
        
    def _initialize_channels(self) -> None:
        """Initialize push channel adapters based on configuration."""
        channel_configs = self.config.get('channels', {})
        
        # Telegram
        if channel_configs.get('telegram', {}).get('enabled', False):
            try:
                self.channels['telegram'] = TelegramChannel(
                    bot_token=channel_configs['telegram']['bot_token'],
                    timeout=channel_configs['telegram'].get('timeout', 10),
                    parse_mode=channel_configs['telegram'].get('parse_mode', 'Markdown'),
                    disable_notification=channel_configs['telegram'].get('disable_notification', False)
                )
                logger.info("telegram_channel_initialized")
            except Exception as e:
                logger.error("telegram_channel_init_failed", error=str(e))
        
        # Discord
        if channel_configs.get('discord', {}).get('enabled', False):
            try:
                self.channels['discord'] = DiscordChannel(
                    webhook_url=channel_configs['discord']['webhook_url'],
                    username=channel_configs['discord'].get('username', 'OpenFi Bot'),
                    avatar_url=channel_configs['discord'].get('avatar_url', ''),
                    timeout=channel_configs['discord'].get('timeout', 10)
                )
                logger.info("discord_channel_initialized")
            except Exception as e:
                logger.error("discord_channel_init_failed", error=str(e))
        
        # Feishu
        if channel_configs.get('feishu', {}).get('enabled', False):
            try:
                self.channels['feishu'] = FeishuChannel(
                    webhook_url=channel_configs['feishu']['webhook_url'],
                    secret=channel_configs['feishu'].get('secret', ''),
                    msg_type=channel_configs['feishu'].get('msg_type', 'interactive'),
                    timeout=channel_configs['feishu'].get('timeout', 10)
                )
                logger.info("feishu_channel_initialized")
            except Exception as e:
                logger.error("feishu_channel_init_failed", error=str(e))
        
        # WeChat Work
        if channel_configs.get('wechat_work', {}).get('enabled', False):
            try:
                self.channels['wechat_work'] = WeChatWorkChannel(
                    webhook_url=channel_configs['wechat_work']['webhook_url'],
                    msgtype=channel_configs['wechat_work'].get('msgtype', 'markdown'),
                    timeout=channel_configs['wechat_work'].get('timeout', 10)
                )
                logger.info("wechat_work_channel_initialized")
            except Exception as e:
                logger.error("wechat_work_channel_init_failed", error=str(e))
        
        # Email
        if channel_configs.get('email', {}).get('enabled', False):
            try:
                self.channels['email'] = EmailChannel(
                    smtp_host=channel_configs['email']['smtp_host'],
                    smtp_port=channel_configs['email']['smtp_port'],
                    smtp_user=channel_configs['email']['smtp_user'],
                    smtp_password=channel_configs['email']['smtp_password'],
                    from_address=channel_configs['email']['from_address'],
                    use_tls=channel_configs['email'].get('use_tls', True),
                    timeout=channel_configs['email'].get('timeout', 30)
                )
                logger.info("email_channel_initialized")
            except Exception as e:
                logger.error("email_channel_init_failed", error=str(e))
        
        logger.info(
            "push_channels_initialized",
            total_channels=len(self.channels),
            channels=list(self.channels.keys())
        )
    
    def _initialize_metrics(self) -> None:
        """Initialize metrics tracking for each channel."""
        for channel_name in self.channels.keys():
            self.metrics[channel_name] = {
                'total_notifications_sent': 0,
                'successful_deliveries': 0,
                'failed_deliveries': 0,
                'total_delivery_time': 0.0
            }
    
    async def start(self) -> None:
        """Start the push notification manager by subscribing to event bus."""
        # Subscribe to high-value signal topic
        await self.event_bus.subscribe(
            "ai.high_value_signal",
            self._handle_high_value_signal
        )
        
        logger.info("push_notification_manager_started", topic="ai.high_value_signal")
    
    async def stop(self) -> None:
        """Stop the push notification manager."""
        # Unsubscribe from event bus
        await self.event_bus.unsubscribe(
            "ai.high_value_signal",
            self._handle_high_value_signal
        )
        
        logger.info("push_notification_manager_stopped")
    
    async def _handle_high_value_signal(self, event: Event) -> None:
        """
        Handle high-value signal event from event bus.
        
        Args:
            event: Event containing high-value signal data
        """
        try:
            payload = event.payload
            
            # Extract signal data
            signal_id = payload.get('signal_id')
            relevance_score = payload.get('relevance_score', 0)
            potential_impact = payload.get('potential_impact', 'low')
            summary = payload.get('summary', '')
            suggested_actions = payload.get('suggested_actions', [])
            related_symbols = payload.get('related_symbols', [])
            timestamp = payload.get('timestamp', datetime.utcnow().isoformat())
            
            logger.info(
                "high_value_signal_received",
                signal_id=signal_id,
                relevance_score=relevance_score,
                potential_impact=potential_impact
            )
            
            # Query all users (in single-user mode, this will be one user)
            # In future multi-user mode, this would filter by user preferences
            async with self.db_session_factory() as session:
                result = await session.execute(select(User))
                users = result.scalars().all()
                
                # Send notifications to all users
                for user in users:
                    # Evaluate signal against user's alert rules
                    should_notify = await self.alert_rule_engine.evaluate_signal(
                        user_id=user.id,
                        signal={
                            'relevance_score': relevance_score,
                            'potential_impact': potential_impact,
                            'related_symbols': related_symbols,
                            'timestamp': timestamp
                        }
                    )
                    
                    if should_notify:
                        await self._send_notification_to_user(
                            session=session,
                            user=user,
                            signal_id=signal_id,
                            relevance_score=relevance_score,
                            potential_impact=potential_impact,
                            summary=summary,
                            suggested_actions=suggested_actions,
                            related_symbols=related_symbols,
                            timestamp=timestamp
                        )
                    else:
                        logger.info(
                            "signal_filtered_by_alert_rules",
                            user_id=str(user.id),
                            signal_id=signal_id,
                            relevance_score=relevance_score
                        )
        
        except Exception as e:
            logger.error("handle_high_value_signal_error", error=str(e))
    
    async def _send_notification_to_user(
        self,
        session: AsyncSession,
        user: User,
        signal_id: Optional[str],
        relevance_score: int,
        potential_impact: str,
        summary: str,
        suggested_actions: list[str],
        related_symbols: list[str],
        timestamp: str
    ) -> None:
        """
        Send notification to a specific user through all enabled channels.
        
        Args:
            session: Database session
            user: User to send notification to
            signal_id: Signal ID
            relevance_score: Relevance score (0-100)
            potential_impact: Impact level (low/medium/high)
            summary: Signal summary
            suggested_actions: List of suggested actions
            related_symbols: List of related trading symbols
            timestamp: Signal timestamp
        """
        # Query user's enabled push channels from database
        # For now, we'll use all available channels
        # In future, this would query user's push_config from database
        enabled_channels = list(self.channels.keys())
        
        # Format notification message
        message = self._format_notification_message(
            relevance_score=relevance_score,
            potential_impact=potential_impact,
            summary=summary,
            suggested_actions=suggested_actions,
            related_symbols=related_symbols,
            timestamp=timestamp
        )
        
        # Send to all enabled channels
        for channel_name in enabled_channels:
            await self._deliver_notification(
                session=session,
                user_id=user.id,
                signal_id=signal_id,
                channel_name=channel_name,
                message=message
            )
    
    def _format_notification_message(
        self,
        relevance_score: int,
        potential_impact: str,
        summary: str,
        suggested_actions: list[str],
        related_symbols: list[str],
        timestamp: str
    ) -> str:
        """
        Format notification message with signal information.
        
        Args:
            relevance_score: Relevance score (0-100)
            potential_impact: Impact level (low/medium/high)
            summary: Signal summary
            suggested_actions: List of suggested actions
            related_symbols: List of related trading symbols
            timestamp: Signal timestamp
            
        Returns:
            Formatted notification message
        """
        # Impact emoji mapping
        impact_emoji = {
            'low': 'ℹ️',
            'medium': '⚠️',
            'high': '🚨'
        }
        
        emoji = impact_emoji.get(potential_impact.lower(), 'ℹ️')
        
        # Build message
        lines = [
            f"{emoji} **High-Value Signal Detected**",
            "",
            f"📊 **Relevance Score:** {relevance_score}/100",
            f"💥 **Potential Impact:** {potential_impact.upper()}",
            ""
        ]
        
        if related_symbols:
            lines.append(f"📈 **Related Symbols:** {', '.join(related_symbols)}")
            lines.append("")
        
        lines.append(f"📝 **Summary:**")
        lines.append(summary)
        lines.append("")
        
        if suggested_actions:
            lines.append(f"💡 **Suggested Actions:**")
            for action in suggested_actions:
                lines.append(f"  • {action}")
            lines.append("")
        
        lines.append(f"🕐 **Timestamp:** {timestamp}")
        
        return "\n".join(lines)
    
    async def _deliver_notification(
        self,
        session: AsyncSession,
        user_id: UUID,
        signal_id: Optional[str],
        channel_name: str,
        message: str,
        retry_count: int = 0
    ) -> None:
        """
        Deliver notification to a specific channel with retry logic.
        
        Args:
            session: Database session
            user_id: User ID
            signal_id: Signal ID
            channel_name: Channel name (telegram, discord, etc.)
            message: Formatted message to send
            retry_count: Current retry attempt (0 = first attempt)
        """
        # Get channel adapter
        channel = self.channels.get(channel_name)
        if not channel:
            logger.warning(
                "channel_not_available",
                channel=channel_name,
                user_id=str(user_id)
            )
            return
        
        # Create notification record
        notification = Notification(
            user_id=user_id,
            signal_id=UUID(signal_id) if signal_id else None,
            channel=channel_name,
            message=message,
            status='pending',
            retry_count=retry_count
        )
        session.add(notification)
        await session.commit()
        await session.refresh(notification)
        
        # Track delivery start time
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Attempt delivery
            # For telegram and discord, we need chat_id/webhook_url from user config
            # For now, we'll use the default from config
            success = await channel.send(message)
            
            if success:
                # Update notification status
                notification.status = 'sent'
                notification.sent_at = datetime.utcnow()
                await session.commit()
                
                # Track metrics
                delivery_time = asyncio.get_event_loop().time() - start_time
                self.metrics[channel_name]['total_notifications_sent'] += 1
                self.metrics[channel_name]['successful_deliveries'] += 1
                self.metrics[channel_name]['total_delivery_time'] += delivery_time
                
                logger.info(
                    "notification_delivered",
                    notification_id=str(notification.id),
                    channel=channel_name,
                    user_id=str(user_id),
                    delivery_time=f"{delivery_time:.2f}s"
                )
            else:
                raise Exception("Channel send returned False")
        
        except Exception as e:
            # Delivery failed
            error_msg = str(e)
            
            # Update notification status
            notification.status = 'failed'
            notification.error_message = error_msg
            await session.commit()
            
            # Track metrics
            self.metrics[channel_name]['total_notifications_sent'] += 1
            self.metrics[channel_name]['failed_deliveries'] += 1
            
            logger.error(
                "notification_delivery_failed",
                notification_id=str(notification.id),
                channel=channel_name,
                user_id=str(user_id),
                retry_count=retry_count,
                error=error_msg
            )
            
            # Retry logic: up to 2 retries with 5-second delay
            max_retries = 2
            retry_delay = 5
            
            if retry_count < max_retries:
                logger.info(
                    "notification_retry_scheduled",
                    notification_id=str(notification.id),
                    channel=channel_name,
                    retry_attempt=retry_count + 1
                )
                
                # Wait before retry
                await asyncio.sleep(retry_delay)
                
                # Retry delivery
                await self._deliver_notification(
                    session=session,
                    user_id=user_id,
                    signal_id=signal_id,
                    channel_name=channel_name,
                    message=message,
                    retry_count=retry_count + 1
                )
            else:
                logger.error(
                    "notification_delivery_failed_max_retries",
                    notification_id=str(notification.id),
                    channel=channel_name,
                    user_id=str(user_id),
                    max_retries=max_retries
                )
    
    def get_metrics(self) -> dict[str, dict[str, Any]]:
        """
        Get delivery metrics for all channels.
        
        Returns:
            Dictionary of metrics per channel
        """
        metrics_with_avg = {}
        
        for channel_name, channel_metrics in self.metrics.items():
            total_sent = channel_metrics['total_notifications_sent']
            successful = channel_metrics['successful_deliveries']
            failed = channel_metrics['failed_deliveries']
            total_time = channel_metrics['total_delivery_time']
            
            # Calculate average delivery time
            avg_delivery_time = (
                total_time / successful if successful > 0 else 0.0
            )
            
            metrics_with_avg[channel_name] = {
                'total_notifications_sent': total_sent,
                'successful_deliveries': successful,
                'failed_deliveries': failed,
                'avg_delivery_time': f"{avg_delivery_time:.2f}s"
            }
        
        return metrics_with_avg
    
    async def handle_bot_command(
        self,
        command_text: str,
        user_id: Optional[UUID] = None,
        channel: Optional[str] = None
    ) -> str:
        """
        Handle bot command from user.
        
        Args:
            command_text: Raw command text from user
            user_id: User ID (optional)
            channel: Channel name (optional)
        
        Returns:
            Formatted response message
        """
        try:
            response = await self.bot_command_handler.handle_command(
                command_text=command_text,
                user_id=str(user_id) if user_id else None,
                channel=channel
            )
            
            return response
        
        except Exception as e:
            logger.error(
                "bot_command_handling_error",
                command=command_text,
                user_id=str(user_id) if user_id else None,
                error=str(e)
            )
            return f"❌ Error processing command: {str(e)}"
