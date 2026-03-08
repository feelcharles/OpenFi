"""
User Center module for OpenFi Lite.

This module provides user and EA profile management APIs and push notification services.
"""

from system_core.user_center.api import router
from system_core.user_center.push_notification_manager import PushNotificationManager
from system_core.user_center.push_channels import (
    PushChannel,
    TelegramChannel,
    DiscordChannel,
    FeishuChannel,
    WeChatWorkChannel,
    EmailChannel
)

__all__ = [
    "router",
    "PushNotificationManager",
    "PushChannel",
    "TelegramChannel",
    "DiscordChannel",
    "FeishuChannel",
    "WeChatWorkChannel",
    "EmailChannel"
]
