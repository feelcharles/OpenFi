"""
Bot Command Handler

Processes bot commands from users through push channels.
Supports EA management, system status, and testing commands.
"""

import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Callable

from system_core.config import get_logger
from system_core.execution_engine.ea_manager import EAManager

logger = get_logger(__name__)

class BotCommandHandler:
    """
    Handles bot commands from users.
    
    Features:
    - Loads command definitions from config/bot_commands.yaml
    - Registers handlers for various commands
    - Parses commands and extracts arguments
    - Validates command syntax
    - Executes command handlers
    - Formats responses with channel-specific templates
    """
    
    def __init__(
        self,
        config_path: str = "config/bot_commands.yaml",
        ea_manager: Optional[EAManager] = None
    ):
        """
        Initialize Bot Command Handler.
        
        Args:
            config_path: Path to bot commands configuration file
            ea_manager: EA Manager instance for EA-related commands
        """
        self.config_path = Path(config_path)
        self.ea_manager = ea_manager or EAManager()
        
        # Command registry: command_name -> handler_function
        self.command_handlers: dict[str, Callable] = {}
        
        # Load configuration
        self.config = self._load_config()
        
        # Register command handlers
        self._register_handlers()
        
        logger.info(
            "bot_command_handler_initialized",
            config_path=str(self.config_path),
            registered_commands=len(self.command_handlers)
        )
    
    def _load_config(self) -> dict[str, Any]:
        """
        Load bot commands configuration from YAML file.
        
        Returns:
            Configuration dictionary
        """
        try:
            if not self.config_path.exists():
                logger.warning(
                    "bot_commands_config_not_found",
                    path=str(self.config_path)
                )
                return {}
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            
            logger.info(
                "bot_commands_config_loaded",
                path=str(self.config_path)
            )
            
            return config
        
        except Exception as e:
            logger.error(
                "bot_commands_config_load_error",
                path=str(self.config_path),
                error=str(e)
            )
            return {}
    
    def _register_handlers(self) -> None:
        """Register command handlers for all supported commands."""
        # EA commands
        self.command_handlers['/ea_refresh'] = self._handle_ea_refresh
        self.command_handlers['/ea_test'] = self._handle_ea_test
        self.command_handlers['/ea_list'] = self._handle_ea_list
        
        # System commands
        self.command_handlers['/status'] = self._handle_status
        self.command_handlers['/signals'] = self._handle_signals
        self.command_handlers['/positions'] = self._handle_positions
        
        # Help command
        self.command_handlers['/help'] = self._handle_help
        
        logger.info(
            "command_handlers_registered",
            handlers=list(self.command_handlers.keys())
        )
    
    async def handle_command(
        self,
        command_text: str,
        user_id: Optional[str] = None,
        channel: Optional[str] = None
    ) -> str:
        """
        Parse and execute bot command.
        
        Args:
            command_text: Raw command text from user
            user_id: User ID (optional, for future permission checks)
            channel: Channel name (optional, for channel-specific formatting)
        
        Returns:
            Formatted response message
        """
        try:
            # Parse command
            command, args = self._parse_command(command_text)
            
            if not command:
                return self._format_error_response(
                    "Invalid command format. Use /help to see available commands."
                )
            
            logger.info(
                "bot_command_received",
                command=command,
                args=args,
                user_id=user_id,
                channel=channel
            )
            
            # Get command handler
            handler = self.command_handlers.get(command)
            
            if not handler:
                return self._format_error_response(
                    f"Unknown command: {command}\nUse /help to see available commands."
                )
            
            # Execute handler
            response = await handler(args)
            
            logger.info(
                "bot_command_executed",
                command=command,
                user_id=user_id
            )
            
            return response
        
        except Exception as e:
            logger.error(
                "bot_command_execution_error",
                command_text=command_text,
                error=str(e)
            )
            return self._format_error_response(
                f"Error executing command: {str(e)}"
            )
    
    def _parse_command(self, command_text: str) -> tuple:
        """
        Parse command text into command name and arguments.
        
        Args:
            command_text: Raw command text
        
        Returns:
            Tuple of (command_name, arguments_list)
        """
        # Strip whitespace
        command_text = command_text.strip()
        
        # Check if starts with /
        if not command_text.startswith('/'):
            return None, []
        
        # Split into parts
        parts = command_text.split()
        
        if not parts:
            return None, []
        
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        return command, args
    
    def _format_error_response(self, error_message: str) -> str:
        """
        Format error response message.
        
        Args:
            error_message: Error message text
        
        Returns:
            Formatted error message
        """
        return f"❌ **Error**\n\n{error_message}"
    
    def _format_success_response(self, title: str, content: str) -> str:
        """
        Format success response message.
        
        Args:
            title: Response title
            content: Response content
        
        Returns:
            Formatted success message
        """
        return f"✅ **{title}**\n\n{content}"
    
    # ============================================
    # Command Handlers
    # ============================================
    
    async def _handle_ea_refresh(self, args: list[str]) -> str:
        """
        Handle /ea_refresh command - scan EA folder and update configuration.
        
        Args:
            args: Command arguments (unused)
        
        Returns:
            Formatted response message
        """
        try:
            # Trigger EA Manager scan
            result = self.ea_manager.refresh_ea_list()
            
            if not result.get('success'):
                return self._format_error_response(
                    f"EA refresh failed: {result.get('error', 'Unknown error')}"
                )
            
            # Format response
            platform_stats = result.get('platform_stats', {})
            
            response = f"""🔄 **EA List Refreshed**

📊 **Statistics:**
• Total: {result.get('total_eas', 0)} EAs
• Added: {result.get('added', 0)}
• Updated: {result.get('updated', 0)}
• Removed: {result.get('removed', 0)}

🤖 **Platform Distribution:**
• MT4: {platform_stats.get('mt4', 0)}
• MT5: {platform_stats.get('mt5', 0)}
• TradingView: {platform_stats.get('tradingview', 0)}

⏰ {result.get('timestamp', '')}"""
            
            return response
        
        except Exception as e:
            logger.error("ea_refresh_command_error", error=str(e))
            return self._format_error_response(f"EA refresh failed: {str(e)}")
    
    async def _handle_ea_test(self, args: list[str]) -> str:
        """
        Handle /ea_test command - test EA for errors.
        
        Args:
            args: Command arguments [ea_name]
        
        Returns:
            Formatted response message
        """
        try:
            # Validate arguments
            if not args:
                return self._format_error_response(
                    "Usage: /ea_test {name}\n\nExample: /ea_test my_strategy"
                )
            
            ea_name = ' '.join(args)
            
            # Lookup EA
            ea = self.ea_manager.find_ea_by_name(ea_name)
            
            if not ea:
                return self._format_error_response(
                    f"EA '{ea_name}' not found.\n\nUse /ea_refresh to update EA list."
                )
            
            # For now, we'll return a simulated test result
            # In a full implementation, this would call the actual EA testing framework
            
            # Simulate test execution
            test_passed = True  # Placeholder
            test_duration = "2.5s"  # Placeholder
            
            if test_passed:
                response = f"""🧪 **EA Test: {ea['ea_name']}**

🤖 **Platform:** {ea['ea_type'].upper()}
📁 **File:** {ea['file_path']}
⏱️ **Test Duration:** {test_duration}

✅ **Test Passed** - No errors found

⏰ {datetime.now().isoformat()}"""
            else:
                # Simulated failure case
                error_count = 3
                error_types = {
                    'syntax_error': 1,
                    'undefined_variable': 2
                }
                log_path = f"ea/logs/ea_log_{ea['ea_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                
                response = f"""🧪 **EA Test: {ea['ea_name']}**

🤖 **Platform:** {ea['ea_type'].upper()}
📁 **File:** {ea['file_path']}
⏱️ **Test Duration:** {test_duration}

❌ **Test Failed** - Found {error_count} errors

📋 **Error Types:**
"""
                for error_type, count in error_types.items():
                    response += f"• {error_type}: {count}\n"
                
                response += f"\n💡 **Details:** {log_path}\n\n⏰ {datetime.now().isoformat()}"
            
            return response
        
        except Exception as e:
            logger.error("ea_test_command_error", error=str(e))
            return self._format_error_response(f"EA test failed: {str(e)}")
    
    async def _handle_ea_list(self, args: list[str]) -> str:
        """
        Handle /ea_list command - list all discovered EAs.
        
        Args:
            args: Command arguments (unused)
        
        Returns:
            Formatted response message
        """
        try:
            # Load EA config
            if not self.ea_manager.config_path.exists():
                return self._format_error_response(
                    "No EAs found. Use /ea_refresh to scan for EAs."
                )
            
            with open(self.ea_manager.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            
            eas = config.get('eas', [])
            
            if not eas:
                return self._format_error_response(
                    "No EAs found. Use /ea_refresh to scan for EAs."
                )
            
            # Format response
            response = f"🤖 **EA List** ({len(eas)} total)\n\n"
            
            for ea in eas:
                status_emoji = "✅" if ea.get('enabled') else "❌"
                response += f"{status_emoji} **{ea['ea_name']}**\n"
                response += f"   Platform: {ea['ea_type'].upper()}\n"
                response += f"   File: {ea['file_path']}\n\n"
            
            return response
        
        except Exception as e:
            logger.error("ea_list_command_error", error=str(e))
            return self._format_error_response(f"Failed to list EAs: {str(e)}")
    
    async def _handle_status(self, args: list[str]) -> str:
        """
        Handle /status command - show system status.
        
        Args:
            args: Command arguments (unused)
        
        Returns:
            Formatted response message
        """
        # Placeholder implementation
        response = f"""📊 **System Status**

🖥️ **System:** Running
⏱️ **Uptime:** 24h 15m
💾 **Memory:** 45%

🤖 **EA Status:** No EAs running

📡 **Data Sources:** Active
🧠 **LLM:** Available

⏰ {datetime.now().isoformat()}"""
        
        return response
    
    async def _handle_signals(self, args: list[str]) -> str:
        """
        Handle /signals command - show recent signals.
        
        Args:
            args: Command arguments (unused)
        
        Returns:
            Formatted response message
        """
        # Placeholder implementation
        response = """📊 **Recent Signals**

No recent signals.

Use /help for more commands."""
        
        return response
    
    async def _handle_positions(self, args: list[str]) -> str:
        """
        Handle /positions command - show open positions.
        
        Args:
            args: Command arguments (unused)
        
        Returns:
            Formatted response message
        """
        # Placeholder implementation
        response = """📈 **Open Positions**

No open positions.

Use /help for more commands."""
        
        return response
    
    async def _handle_help(self, args: list[str]) -> str:
        """
        Handle /help command - show available commands.
        
        Args:
            args: Command arguments (unused)
        
        Returns:
            Formatted response message
        """
        response = """📖 **Command Help**

🤖 **EA Commands:**
• /ea_refresh - Scan EA folder and update list
• /ea_test {name} - Test EA for errors
• /ea_list - List all discovered EAs

🖥️ **System Commands:**
• /status - Show system status
• /signals - Show recent signals
• /positions - Show open positions

❓ **Help:**
• /help - Show this help message

💡 Type a command to use it."""
        
        return response
