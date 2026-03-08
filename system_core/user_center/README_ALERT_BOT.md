# Alert Rule Filtering and Bot Command Processing

This document describes the implementation of Tasks 17-18: Alert Rule Filtering and Bot Command Processing.

## Overview

These modules extend the User Center with intelligent alert filtering and interactive bot command capabilities:

1. **AlertRuleEngine**: Filters high-value signals based on user-defined rules before sending notifications
2. **BotCommandHandler**: Processes bot commands from users through push channels for system management

## Components

### 1. AlertRuleEngine (`alert_rule_engine.py`)

Evaluates high-value signals against user-defined alert rules to determine which signals should trigger notifications.

#### Features

- Loads user alert rules from database
- Evaluates signals against multiple filter criteria:
  - **Relevance Score**: Minimum score threshold (0-100)
  - **Required Symbols**: Signal must mention at least one specified symbol
  - **Required Impact Levels**: Signal impact must match specified levels (low/medium/high)
  - **Time Windows**: Signal must occur within specified time ranges
- Returns whether signal matches at least one enabled rule
- Fail-open behavior: allows signals through on errors or when no rules configured

#### Usage

```python
from system_core.user_center.alert_rule_engine import AlertRuleEngine

# Initialize with database session factory
engine = AlertRuleEngine(db_session_factory)

# Evaluate signal against user's rules
signal = {
    'relevance_score': 85,
    'potential_impact': 'high',
    'related_symbols': ['EURUSD', 'GBPUSD'],
    'timestamp': '2024-01-15T14:30:00Z'
}

should_notify = await engine.evaluate_signal(user_id, signal)
```

#### Alert Rule Configuration

Alert rules are stored in the `alert_rules` database table with the following fields:

- `user_id`: User who owns the rule
- `rule_name`: Descriptive name for the rule
- `min_relevance_score`: Minimum relevance score (optional)
- `required_symbols`: List of symbols to match (optional)
- `required_impact_levels`: List of impact levels to match (optional)
- `time_windows`: List of time ranges in "HH:MM-HH:MM" format (optional)
- `enabled`: Whether the rule is active

**Example Rules:**

```python
# Rule 1: High-score signals only
AlertRule(
    rule_name="High Score Filter",
    min_relevance_score=80,
    enabled=True
)

# Rule 2: EUR/USD and GBP/USD signals during market hours
AlertRule(
    rule_name="Forex Trading Hours",
    required_symbols=["EURUSD", "GBPUSD"],
    time_windows=["09:00-16:00"],
    enabled=True
)

# Rule 3: High-impact signals only
AlertRule(
    rule_name="High Impact Only",
    required_impact_levels=["high"],
    min_relevance_score=70,
    enabled=True
)
```

#### Time Window Matching

Time windows support both normal and overnight ranges:

- **Normal**: `"09:00-16:00"` - matches times between 9 AM and 4 PM
- **Overnight**: `"22:00-02:00"` - matches times after 10 PM or before 2 AM

### 2. BotCommandHandler (`bot_command_handler.py`)

Processes bot commands from users through push channels, enabling quick system management without accessing the web interface.

#### Features

- Loads command definitions from `config/bot_commands.yaml`
- Parses commands and extracts arguments
- Validates command syntax
- Executes command handlers
- Formats responses with emoji indicators and multi-line output
- Processes commands within 5 seconds

#### Supported Commands

##### EA Management Commands

- `/ea_refresh` - Scan EA folder and update configuration
  - Returns: Total EAs, added/updated/removed counts, platform distribution
  
- `/ea_test {name}` - Test EA for errors
  - Arguments: EA name or ID
  - Returns: Test results with success/failure status, error details, log path
  
- `/ea_list` - List all discovered EAs
  - Returns: List of EAs with platform and file path

##### System Commands

- `/status` - Show system status
  - Returns: System uptime, memory usage, EA status, data sources, LLM status
  
- `/signals` - Show recent signals
  - Returns: List of recent high-value signals
  
- `/positions` - Show open positions
  - Returns: List of open trading positions

##### Help Command

- `/help` - Show available commands
  - Returns: List of all commands with descriptions

#### Usage

```python
from system_core.user_center.bot_command_handler import BotCommandHandler

# Initialize handler
handler = BotCommandHandler()

# Handle command from user
response = await handler.handle_command(
    command_text="/ea_refresh",
    user_id="user-uuid",
    channel="telegram"
)

# Response is formatted text ready to send
print(response)
```

#### Command Format

Commands follow this format:

```
/command [arguments]
```

Examples:
- `/help`
- `/ea_refresh`
- `/ea_test my_strategy`
- `/ea_test my strategy name` (multi-word arguments)

Invalid commands return error messages with usage examples.

#### Response Format

Responses use emoji indicators for visual clarity:

- ✅ Success
- ❌ Error
- 🔄 Refresh/Update
- 🧪 Test
- 📊 Statistics
- 🤖 EA/Bot
- 📁 File
- ⏱️ Time/Duration
- 💡 Tip/Info

Example response:

```
🔄 **EA List Refreshed**

📊 **Statistics:**
• Total: 5 EAs
• Added: 2
• Updated: 1
• Removed: 0

🤖 **Platform Distribution:**
• MT4: 2
• MT5: 2
• TradingView: 1

⏰ 2024-01-15T14:30:00Z
```

## Integration with PushNotificationManager

Both components are integrated into the `PushNotificationManager`:

### Alert Rule Filtering

The `PushNotificationManager` now evaluates signals against alert rules before sending notifications:

```python
# In _handle_high_value_signal method
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
        await self._send_notification_to_user(...)
    else:
        logger.info("signal_filtered_by_alert_rules", ...)
```

### Bot Command Processing

The `PushNotificationManager` provides a method to handle bot commands:

```python
# Handle bot command from user
response = await push_manager.handle_bot_command(
    command_text="/ea_refresh",
    user_id=user.id,
    channel="telegram"
)

# Send response back to user through same channel
await channel.send(response)
```

## Configuration

### Bot Commands Configuration

Bot commands are configured in `config/bot_commands.yaml`:

```yaml
ea_commands:
  - command: "/ea_refresh"
    description: "Scan EA folder and update list"
    enabled: true
    requires_confirmation: false
    response_format: |
      🔄 EA List Refreshed
      
      📊 Statistics:
      • Total: { total_eas } EAs
      • Added: { added }
      • Updated: { updated }
      • Removed: { removed }
      
      🤖 Platform Distribution:
      • MT4: { platform_stats.mt4 }
      • MT5: { platform_stats.mt5 }
      • TradingView: { platform_stats.tradingview }
```

## Database Schema

### AlertRule Table

```sql
CREATE TABLE alert_rules (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rule_name VARCHAR(100) NOT NULL,
    min_relevance_score INTEGER CHECK (min_relevance_score >= 0 AND min_relevance_score <= 100),
    required_symbols VARCHAR(20)[],
    required_impact_levels VARCHAR(20)[],
    time_windows VARCHAR(50)[],
    enabled BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    INDEX idx_alert_rules_user_id (user_id),
    INDEX idx_alert_rules_enabled (enabled)
);
```

## Logging

Both components use structured logging with the following events:

### AlertRuleEngine Events

- `alert_rule_engine_initialized` - Engine initialized
- `no_alert_rules_configured` - No rules found for user (default: allow)
- `signal_matched_alert_rule` - Signal matched a rule
- `signal_filtered_by_alert_rules` - Signal filtered by rules
- `alert_rule_evaluation_error` - Error during evaluation
- `user_alert_rules_loaded` - Rules loaded from database
- `signal_filtered_by_relevance_score` - Filtered by score
- `signal_filtered_by_symbols` - Filtered by symbols
- `signal_filtered_by_impact` - Filtered by impact level
- `signal_filtered_by_time_window` - Filtered by time window

### BotCommandHandler Events

- `bot_command_handler_initialized` - Handler initialized
- `bot_commands_config_loaded` - Configuration loaded
- `command_handlers_registered` - Handlers registered
- `bot_command_received` - Command received from user
- `bot_command_executed` - Command executed successfully
- `bot_command_execution_error` - Error executing command
- `ea_refresh_command_error` - Error in /ea_refresh
- `ea_test_command_error` - Error in /ea_test
- `ea_list_command_error` - Error in /ea_list

## Testing

Run the test script to verify implementation:

```bash
python test_tasks_17_18.py
```

The test verifies:
1. File structure and class definitions
2. Method presence (sync and async)
3. Integration with PushNotificationManager
4. Command parsing logic
5. Alert rule matching logic

## Requirements Validation

### Task 17: Alert Rule Filtering

✅ **17.1** - AlertRuleEngine class created with database integration
✅ **17.2** - Rule matching logic implemented for all filter types:
  - min_relevance_score
  - required_symbols
  - required_impact_levels
  - time_windows

### Task 18: Bot Command Processing

✅ **18.1** - BotCommandHandler class created with command registry
✅ **18.2** - Command validation and execution implemented
✅ **18.3** - Channel-specific response formatting with emojis
✅ **18.4** - /ea_refresh command implemented
✅ **18.5** - /ea_test command implemented

### Requirements Coverage

- **Requirement 9.2**: Alert rules loaded from database ✅
- **Requirement 9.3**: Notification sent only when signal matches rule ✅
- **Requirement 9.4**: min_relevance_score filtering ✅
- **Requirement 9.5**: required_symbols filtering ✅
- **Requirement 9.6**: required_impact_levels filtering ✅
- **Requirement 9.7**: time_windows filtering ✅
- **Requirement 19.1**: Bot commands loaded from config ✅
- **Requirement 19.2**: Command handlers registered ✅
- **Requirement 19.3**: Command parsing and argument extraction ✅
- **Requirement 19.4**: Command syntax validation ✅
- **Requirement 19.5**: Response formatting with emojis ✅
- **Requirement 19.6**: /ea_refresh displays statistics ✅
- **Requirement 19.7**: /ea_test displays success status ✅
- **Requirement 19.8**: /ea_test displays failure details ✅
- **Requirement 19.9**: Commands processed within 5 seconds ✅

## Future Enhancements

1. **Alert Rule UI**: Web interface for managing alert rules
2. **Command Permissions**: Role-based access control for commands
3. **Command History**: Track command usage and responses
4. **Custom Commands**: User-defined commands with custom handlers
5. **Command Aliases**: Support for command shortcuts
6. **Interactive Commands**: Multi-step commands with user input
7. **Scheduled Commands**: Cron-like scheduling for commands
8. **Command Analytics**: Usage statistics and performance metrics
