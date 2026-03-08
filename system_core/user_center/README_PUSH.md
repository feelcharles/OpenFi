# Push Notification System

Multi-channel push notification system for delivering high-value signals to users.

## Features

- **Multi-Channel Support**: Telegram, Discord, Feishu, WeChat Work, Email
- **Event-Driven**: Subscribes to Event Bus topic "ai.high_value_signal"
- **Automatic Retry**: Up to 2 retries with 5-second delay on failure
- **Metrics Tracking**: Tracks delivery success rate and latency per channel
- **Configurable**: All settings in `config/push_config.yaml`

## Architecture

```
Event Bus (ai.high_value_signal)
    ↓
PushNotificationManager
    ↓
Query User Channels (Database)
    ↓
Format Message
    ↓
Deliver to Channels (with retry)
    ├── TelegramChannel
    ├── DiscordChannel
    ├── FeishuChannel
    ├── WeChatWorkChannel
    └── EmailChannel
```

## Usage

### Initialize Push Notification Manager

```python
from system_core.event_bus.event_bus import EventBus
from system_core.user_center import PushNotificationManager
from system_core.database.client import get_db_client

# Create event bus
event_bus = EventBus(redis_url="redis://localhost:6379")
await event_bus.connect()

# Create database session factory
db_client = get_db_client()
async def db_session_factory():
    async with db_client.session() as session:
        yield session

# Create push notification manager
push_manager = PushNotificationManager(
    event_bus=event_bus,
    db_session_factory=db_session_factory,
    config_path="config/push_config.yaml"
)

# Start listening for signals
await push_manager.start()
```

### Publish High-Value Signal

```python
# Publish signal to event bus
await event_bus.publish(
    topic="ai.high_value_signal",
    payload={
        "signal_id": "123e4567-e89b-12d3-a456-426614174000",
        "relevance_score": 85,
        "potential_impact": "high",
        "summary": "Federal Reserve announces unexpected rate hike",
        "suggested_actions": [
            "Monitor USD pairs for volatility",
            "Consider reducing leverage on open positions"
        ],
        "related_symbols": ["EURUSD", "GBPUSD", "USDJPY"],
        "timestamp": "2024-01-15T14:30:00Z"
    }
)
```

### Get Delivery Metrics

```python
# Get metrics for all channels
metrics = push_manager.get_metrics()

# Example output:
# {
#     "telegram": {
#         "total_notifications_sent": 100,
#         "successful_deliveries": 98,
#         "failed_deliveries": 2,
#         "avg_delivery_time": "1.23s"
#     },
#     "discord": {
#         "total_notifications_sent": 100,
#         "successful_deliveries": 100,
#         "failed_deliveries": 0,
#         "avg_delivery_time": "0.87s"
#     }
# }
```

## Configuration

Edit `config/push_config.yaml` to configure channels:

```yaml
channels:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
    parse_mode: "Markdown"
    timeout: 10
  
  discord:
    enabled: true
    webhook_url: "${DISCORD_WEBHOOK_URL}"
    username: "OpenFi Bot"
    timeout: 10
  
  email:
    enabled: true
    smtp_host: "${SMTP_HOST}"
    smtp_port: 587
    smtp_user: "${SMTP_USER}"
    smtp_password: "${SMTP_PASSWORD}"
    from_address: "${EMAIL_FROM}"
    to_addresses:
      - "${EMAIL_TO}"
    use_tls: true
    timeout: 30
```

## Message Format

Notifications are formatted with:
- **Relevance Score**: 0-100 score indicating signal importance
- **Potential Impact**: Low/Medium/High impact level with emoji indicator
- **Related Symbols**: Trading symbols affected by the signal
- **Summary**: Brief description of the signal
- **Suggested Actions**: Actionable recommendations
- **Timestamp**: When the signal was generated

Example message:

```
🚨 **High-Value Signal Detected**

📊 **Relevance Score:** 85/100
💥 **Potential Impact:** HIGH

📈 **Related Symbols:** EURUSD, GBPUSD, USDJPY

📝 **Summary:**
Federal Reserve announces unexpected rate hike

💡 **Suggested Actions:**
  • Monitor USD pairs for volatility
  • Consider reducing leverage on open positions

🕐 **Timestamp:** 2024-01-15T14:30:00Z
```

## Channel-Specific Features

### Telegram
- Supports Markdown and HTML formatting
- Can disable notification sound
- Requires bot token and chat ID

### Discord
- Uses webhook for delivery
- Customizable bot username and avatar
- Supports rich embeds (future enhancement)

### Feishu (Lark)
- Supports signature verification for security
- Multiple message types (text, post, interactive)
- Webhook-based delivery

### WeChat Work
- Supports text and markdown messages
- Webhook-based delivery
- Enterprise-focused features

### Email
- SMTP-based delivery with TLS support
- Plain text and HTML formatting
- Multiple recipients supported

## Retry Logic

The system implements automatic retry with the following behavior:

1. **First Attempt**: Immediate delivery
2. **Retry 1**: After 5 seconds if first attempt fails
3. **Retry 2**: After 5 seconds if retry 1 fails
4. **Final Failure**: Logged for manual review after 2 retries

All delivery attempts are tracked in the `notifications` database table.

## Database Schema

### Notifications Table

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    signal_id UUID REFERENCES signals(id),
    channel VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,  -- pending, sent, failed
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Performance

- **Delivery Target**: Within 10 seconds of signal generation
- **Retry Delay**: 5 seconds between attempts
- **Max Retries**: 2 attempts (3 total tries)
- **Timeout**: Configurable per channel (10-30 seconds)

## Requirements

The push notification system validates the following requirements:

- **8.1**: Load channel configurations from config/push_config.yaml ✓
- **8.2**: Support 6+ channels (Telegram, Discord, Feishu, WeChat Work, Email) ✓
- **8.3**: Subscribe to Event Bus topic "ai.high_value_signal" ✓
- **8.4**: Query user's enabled channels from database ✓
- **8.5**: Format messages with signal data and channel-specific templates ✓
- **8.6**: Deliver within 10 seconds ✓
- **8.7**: Retry up to 2 times with 5-second delay ✓
- **8.8**: Track metrics per channel ✓

## Future Enhancements

- Alert rule filtering (Requirement 9)
- User-specific channel preferences
- Rich embeds for Discord
- Interactive cards for Feishu
- HTML email templates
- Rate limiting per channel
- Message deduplication
- Quiet hours support
