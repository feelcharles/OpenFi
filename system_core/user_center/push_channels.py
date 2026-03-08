"""
Push Channel Adapters

Implements channel-specific adapters for delivering push notifications.
Supports: Telegram, Discord, Feishu, WeChat Work, Email.
"""

import asyncio
import hashlib
import hmac
import json
import time
from abc import ABC, abstractmethod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import aiohttp
import aiosmtplib

from system_core.config import get_logger

logger = get_logger(__name__)

class PushChannel(ABC):
    """Abstract base class for push channel adapters."""
    
    @abstractmethod
    async def send(self, message: str, **kwargs) -> bool:
        """
        Send message through channel.
        
        Args:
            message: Message content to send
            **kwargs: Channel-specific parameters
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """
        Validate channel configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        pass

class TelegramChannel(PushChannel):
    """Telegram Bot API channel adapter."""
    
    def __init__(
        self,
        bot_token: str,
        timeout: int = 10,
        parse_mode: str = "Markdown",
        disable_notification: bool = False
    ):
        """
        Initialize Telegram channel.
        
        Args:
            bot_token: Telegram bot token
            timeout: Request timeout in seconds
            parse_mode: Message parse mode (Markdown, HTML, None)
            disable_notification: Disable notification sound
        """
        self.bot_token = bot_token
        self.timeout = timeout
        self.parse_mode = parse_mode
        self.disable_notification = disable_notification
        self.api_base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def validate_config(self) -> bool:
        """Validate Telegram configuration."""
        return bool(self.bot_token)
    
    async def send(self, message: str, chat_id: Optional[str] = None, **kwargs) -> bool:
        """
        Send message via Telegram Bot API.
        
        Args:
            message: Message content
            chat_id: Telegram chat ID (optional, can be in kwargs)
            **kwargs: Additional parameters
            
        Returns:
            True if successful, False otherwise
        """
        if not self.validate_config():
            logger.error("telegram_invalid_config")
            return False
        
        # Get chat_id from kwargs if not provided
        if not chat_id:
            chat_id = kwargs.get('chat_id')
        
        if not chat_id:
            logger.error("telegram_missing_chat_id")
            return False
        
        try:
            # Prepare request payload
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': self.parse_mode,
                'disable_notification': self.disable_notification
            }
            
            # Send request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base_url}/sendMessage",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        logger.info("telegram_message_sent", chat_id=chat_id)
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            "telegram_send_failed",
                            status=response.status,
                            error=error_text
                        )
                        return False
        
        except asyncio.TimeoutError:
            logger.error("telegram_timeout", timeout=self.timeout)
            return False
        except Exception as e:
            logger.error("telegram_send_error", error=str(e))
            return False

class DiscordChannel(PushChannel):
    """Discord Webhook channel adapter."""
    
    def __init__(
        self,
        webhook_url: str,
        username: str = "OpenFi Bot",
        avatar_url: str = "",
        timeout: int = 10
    ):
        """
        Initialize Discord channel.
        
        Args:
            webhook_url: Discord webhook URL
            username: Bot username to display
            avatar_url: Bot avatar URL
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.username = username
        self.avatar_url = avatar_url
        self.timeout = timeout
    
    def validate_config(self) -> bool:
        """Validate Discord configuration."""
        return bool(self.webhook_url)
    
    async def send(self, message: str, **kwargs) -> bool:
        """
        Send message via Discord webhook.
        
        Args:
            message: Message content
            **kwargs: Additional parameters
            
        Returns:
            True if successful, False otherwise
        """
        if not self.validate_config():
            logger.error("discord_invalid_config")
            return False
        
        try:
            # Prepare request payload
            payload = {
                'content': message,
                'username': self.username
            }
            
            if self.avatar_url:
                payload['avatar_url'] = self.avatar_url
            
            # Send request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status in (200, 204):
                        logger.info("discord_message_sent")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(
                            "discord_send_failed",
                            status=response.status,
                            error=error_text
                        )
                        return False
        
        except asyncio.TimeoutError:
            logger.error("discord_timeout", timeout=self.timeout)
            return False
        except Exception as e:
            logger.error("discord_send_error", error=str(e))
            return False

class FeishuChannel(PushChannel):
    """Feishu (Lark) Webhook channel adapter."""
    
    def __init__(
        self,
        webhook_url: str,
        secret: str = "",
        msg_type: str = "interactive",
        timeout: int = 10
    ):
        """
        Initialize Feishu channel.
        
        Args:
            webhook_url: Feishu webhook URL
            secret: Webhook secret for signature verification
            msg_type: Message type (text, post, interactive)
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.secret = secret
        self.msg_type = msg_type
        self.timeout = timeout
    
    def validate_config(self) -> bool:
        """Validate Feishu configuration."""
        return bool(self.webhook_url)
    
    def _generate_signature(self, timestamp: int) -> str:
        """
        Generate signature for Feishu webhook.
        
        Args:
            timestamp: Current timestamp in seconds
            
        Returns:
            Base64-encoded signature
        """
        if not self.secret:
            return ""
        
        # Concatenate timestamp and secret
        string_to_sign = f"{timestamp}\n{self.secret}"
        
        # Generate HMAC-SHA256 signature
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        
        # Base64 encode
        import base64
        return base64.b64encode(hmac_code).decode('utf-8')
    
    async def send(self, message: str, **kwargs) -> bool:
        """
        Send message via Feishu webhook.
        
        Args:
            message: Message content
            **kwargs: Additional parameters
            
        Returns:
            True if successful, False otherwise
        """
        if not self.validate_config():
            logger.error("feishu_invalid_config")
            return False
        
        try:
            # Generate timestamp and signature
            timestamp = int(time.time())
            signature = self._generate_signature(timestamp)
            
            # Prepare request payload
            payload = {
                'msg_type': 'text',
                'content': {
                    'text': message
                }
            }
            
            # Add signature if secret is configured
            if self.secret:
                payload['timestamp'] = str(timestamp)
                payload['sign'] = signature
            
            # Send request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('code') == 0:
                            logger.info("feishu_message_sent")
                            return True
                        else:
                            logger.error(
                                "feishu_send_failed",
                                code=result.get('code'),
                                msg=result.get('msg')
                            )
                            return False
                    else:
                        error_text = await response.text()
                        logger.error(
                            "feishu_send_failed",
                            status=response.status,
                            error=error_text
                        )
                        return False
        
        except asyncio.TimeoutError:
            logger.error("feishu_timeout", timeout=self.timeout)
            return False
        except Exception as e:
            logger.error("feishu_send_error", error=str(e))
            return False

class WeChatWorkChannel(PushChannel):
    """WeChat Work Webhook channel adapter."""
    
    def __init__(
        self,
        webhook_url: str,
        msgtype: str = "markdown",
        timeout: int = 10
    ):
        """
        Initialize WeChat Work channel.
        
        Args:
            webhook_url: WeChat Work webhook URL
            msgtype: Message type (text, markdown, news)
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.msgtype = msgtype
        self.timeout = timeout
    
    def validate_config(self) -> bool:
        """Validate WeChat Work configuration."""
        return bool(self.webhook_url)
    
    async def send(self, message: str, **kwargs) -> bool:
        """
        Send message via WeChat Work webhook.
        
        Args:
            message: Message content
            **kwargs: Additional parameters
            
        Returns:
            True if successful, False otherwise
        """
        if not self.validate_config():
            logger.error("wechat_work_invalid_config")
            return False
        
        try:
            # Prepare request payload
            if self.msgtype == "markdown":
                payload = {
                    'msgtype': 'markdown',
                    'markdown': {
                        'content': message
                    }
                }
            else:  # text
                payload = {
                    'msgtype': 'text',
                    'text': {
                        'content': message
                    }
                }
            
            # Send request
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('errcode') == 0:
                            logger.info("wechat_work_message_sent")
                            return True
                        else:
                            logger.error(
                                "wechat_work_send_failed",
                                errcode=result.get('errcode'),
                                errmsg=result.get('errmsg')
                            )
                            return False
                    else:
                        error_text = await response.text()
                        logger.error(
                            "wechat_work_send_failed",
                            status=response.status,
                            error=error_text
                        )
                        return False
        
        except asyncio.TimeoutError:
            logger.error("wechat_work_timeout", timeout=self.timeout)
            return False
        except Exception as e:
            logger.error("wechat_work_send_error", error=str(e))
            return False

class EmailChannel(PushChannel):
    """Email SMTP channel adapter."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_address: str,
        use_tls: bool = True,
        timeout: int = 30
    ):
        """
        Initialize Email channel.
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_user: SMTP username
            smtp_password: SMTP password
            from_address: From email address
            use_tls: Use TLS encryption
            timeout: Request timeout in seconds
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_address = from_address
        self.use_tls = use_tls
        self.timeout = timeout
    
    def validate_config(self) -> bool:
        """Validate Email configuration."""
        return all([
            self.smtp_host,
            self.smtp_port,
            self.smtp_user,
            self.smtp_password,
            self.from_address
        ])
    
    async def send(
        self,
        message: str,
        to_addresses: Optional[list[str]] = None,
        subject: str = "OpenFi Alert",
        **kwargs
    ) -> bool:
        """
        Send message via SMTP email.
        
        Args:
            message: Message content
            to_addresses: List of recipient email addresses
            subject: Email subject
            **kwargs: Additional parameters
            
        Returns:
            True if successful, False otherwise
        """
        if not self.validate_config():
            logger.error("email_invalid_config")
            return False
        
        if not to_addresses:
            to_addresses = kwargs.get('to_addresses', [])
        
        if not to_addresses:
            logger.error("email_missing_recipients")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_address
            msg['To'] = ', '.join(to_addresses)
            
            # Add plain text and HTML parts
            text_part = MIMEText(message, 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Send email
            if self.use_tls:
                await aiosmtplib.send(
                    msg,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_user,
                    password=self.smtp_password,
                    use_tls=True,
                    timeout=self.timeout
                )
            else:
                await aiosmtplib.send(
                    msg,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_user,
                    password=self.smtp_password,
                    timeout=self.timeout
                )
            
            logger.info("email_sent", to_addresses=to_addresses)
            return True
        
        except asyncio.TimeoutError:
            logger.error("email_timeout", timeout=self.timeout)
            return False
        except Exception as e:
            logger.error("email_send_error", error=str(e))
            return False
