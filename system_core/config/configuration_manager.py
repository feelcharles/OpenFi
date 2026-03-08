"""
Configuration Manager with Hot Reload Support

Monitors configuration files using watchdog library and provides
automatic reload capabilities with validation.

Validates: Requirements 22.2, 22.3
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4
import queue
import threading

import yaml
from pydantic import ValidationError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from system_core.core.exceptions import ConfigurationError
from system_core.config.schemas import CONFIG_SCHEMAS

logger = logging.getLogger(__name__)

class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration files."""
    
    def __init__(self, manager: 'ConfigurationManager'):
        """
        Initialize file handler.
        
        Args:
            manager: ConfigurationManager instance
        """
        self.manager = manager
        self._last_modified: dict[str, float] = {}
        self._debounce_seconds = 1.0  # Debounce file events
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        """
        Handle file modification events.
        
        Args:
            event: File system event
        """
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Check if this is a monitored file
        if file_path.name not in self.manager.watched_files:
            return
        
        # Debounce: ignore if modified too recently
        current_time = datetime.now().timestamp()
        last_modified = self._last_modified.get(file_path.name, 0)
        
        if current_time - last_modified < self._debounce_seconds:
            return
        
        self._last_modified[file_path.name] = current_time
        
        # Trigger reload via queue (thread-safe)
        logger.info(f"Configuration file modified: {file_path.name}")
        self.manager._reload_queue.put(file_path.name)

class ConfigurationManager:
    """
    Configuration Manager with hot reload support.
    
    Monitors configuration files using watchdog library and automatically
    reloads configurations when files are modified.
    """
    
    # Files to monitor
    WATCHED_FILES = {
        'fetch_sources.yaml',
        'llm_config.yaml',
        'push_config.yaml',
        'prompt_templates.yaml',
        'external_tools.yaml'
    }
    
    def __init__(
        self,
        config_dir: str = "config",
        event_bus: Optional[Any] = None
    ):
        """
        Initialize Configuration Manager.
        
        Args:
            config_dir: Directory containing configuration files
            event_bus: Event bus instance for publishing reload events
        """
        self.config_dir = Path(config_dir)
        self.event_bus = event_bus
        
        # Watched files
        self.watched_files: set[str] = self.WATCHED_FILES.copy()
        
        # Configuration cache
        self._configs: dict[str, dict[str, Any]] = {}
        
        # File watcher
        self._observer: Optional[Observer] = None
        self._handler: Optional[ConfigFileHandler] = None
        
        # Reload queue for thread-safe communication
        self._reload_queue: queue.Queue = queue.Queue()
        self._reload_processor_task: Optional[asyncio.Task] = None
        self._stop_processor = False
        
        # Reload callbacks
        self._callbacks: dict[str, list[Callable]] = {}
        
        # Statistics
        self._reload_count: dict[str, int] = {}
        self._last_reload: dict[str, datetime] = {}
        self._validation_errors: dict[str, list[str]] = {}
        
        logger.info(f"ConfigurationManager initialized with config_dir: {self.config_dir}")
    
    def start(self) -> None:
        """
        Start monitoring configuration files.
        
        Raises:
            ConfigurationError: If config directory doesn't exist
        """
        if not self.config_dir.exists():
            raise ConfigurationError(f"Config directory not found: {self.config_dir}")
        
        # Load initial configurations
        for filename in self.watched_files:
            try:
                self._load_config(filename)
            except Exception as e:
                logger.error(f"Failed to load initial config {filename}: {e}")
        
        # Start file watcher
        self._handler = ConfigFileHandler(self)
        self._observer = Observer()
        self._observer.schedule(
            self._handler,
            str(self.config_dir),
            recursive=False
        )
        self._observer.start()
        
        logger.info(f"Started monitoring {len(self.watched_files)} configuration files")
    
    async def initialize(self) -> None:
        """
        Initialize configuration manager (alias for start_async).
        
        This method is provided for backward compatibility.
        
        Raises:
            ConfigurationError: If config directory doesn't exist
        """
        await self.start_async()
    
    async def close(self) -> None:
        """
        Close configuration manager (alias for stop).
        
        This method is provided for backward compatibility.
        """
        self.stop()
    
    async def start_async(self) -> None:
        """
        Start monitoring configuration files with async reload processor.
        
        Raises:
            ConfigurationError: If config directory doesn't exist
        """
        # Start synchronous monitoring
        self.start()
        
        # Start async reload processor
        self._stop_processor = False
        self._reload_processor_task = asyncio.create_task(self._process_reload_queue())
    
    async def _process_reload_queue(self) -> None:
        """Process reload requests from the queue."""
        while not self._stop_processor:
            try:
                # Check queue with timeout
                try:
                    filename = self._reload_queue.get(timeout=0.1)
                    await self.reload_config(filename)
                except queue.Empty:
                    pass
                
                # Small sleep to prevent busy waiting
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error processing reload queue: {e}")
    
    def stop(self) -> None:
        """Stop monitoring configuration files."""
        # Stop reload processor
        self._stop_processor = True
        if self._reload_processor_task and not self._reload_processor_task.done():
            self._reload_processor_task.cancel()
        
        # Stop file watcher
        if self._observer:
            self._observer.stop()
            self._observer.join()
            logger.info("Stopped configuration file monitoring")
    
    def _load_config(self, filename: str) -> dict[str, Any]:
        """
        Load configuration from file using PyYAML safe_load.
        
        Args:
            filename: Configuration file name
            
        Returns:
            Parsed configuration dictionary
            
        Raises:
            ConfigurationError: If file cannot be loaded or parsed
            
        Validates: Requirements 31.1
        """
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            raise ConfigurationError(f"Configuration file not found: {filename}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Use safe_load for security (Requirement 31.1)
                config = yaml.safe_load(f)
            
            if config is None:
                config = {}
            
            # Cache the configuration
            self._configs[filename] = config
            
            logger.debug(f"Loaded configuration from {filename}")
            return config
            
        except yaml.YAMLError as e:
            # Extract line and column information if available
            error_msg = f"Failed to parse YAML in {filename}"
            if hasattr(e, 'problem_mark'):
                mark = e.problem_mark
                error_msg += f" at line {mark.line + 1}, column {mark.column + 1}"
            error_msg += f": {e}"
            raise ConfigurationError(error_msg)
        except Exception as e:
            raise ConfigurationError(f"Failed to load {filename}: {e}")
    
    def _validate_config(self, filename: str, config: dict[str, Any]) -> bool:
        """
        Validate configuration structure using Pydantic models.
        
        Args:
            filename: Configuration file name
            config: Configuration dictionary
            
        Returns:
            True if valid, False otherwise
            
        Validates: Requirements 31.2, 31.5, 31.6
        """
        errors = []
        
        try:
            # Basic validation - check if it's a dictionary
            if not isinstance(config, dict):
                errors.append("Configuration must be a dictionary")
                self._validation_errors[filename] = errors
                return False
            
            # Use Pydantic model for validation if available
            if filename in CONFIG_SCHEMAS:
                schema_class = CONFIG_SCHEMAS[filename]
                try:
                    # Validate using Pydantic model (Requirement 31.2)
                    schema_class(**config)
                    # Validation successful
                    self._validation_errors[filename] = []
                    return True
                except ValidationError as e:
                    # Extract validation errors with field paths (Requirement 31.6)
                    for error in e.errors():
                        field_path = '.'.join(str(loc) for loc in error['loc'])
                        error_msg = f"Field '{field_path}': {error['msg']}"
                        if 'type' in error:
                            error_msg += f" (expected type: {error['type']})"
                        errors.append(error_msg)
                    
                    self._validation_errors[filename] = errors
                    logger.warning(f"Pydantic validation errors in {filename}: {errors}")
                    return False
            
            # Fallback to basic validation for files without Pydantic schemas
            if filename == 'fetch_sources.yaml':
                if 'sources' not in config:
                    errors.append("Missing required field: sources")
                elif not isinstance(config['sources'], list):
                    errors.append("Field 'sources' must be a list")
                else:
                    # Validate each source
                    for idx, source in enumerate(config['sources']):
                        if not isinstance(source, dict):
                            errors.append(f"Source at index {idx} must be a dictionary")
                            continue
                        
                        required_fields = ['source_id', 'source_type', 'api_endpoint']
                        for field in required_fields:
                            if field not in source:
                                errors.append(f"Source at index {idx} missing required field: {field}")
            
            elif filename == 'llm_config.yaml':
                if 'providers' not in config:
                    errors.append("Missing required field: providers")
                elif not isinstance(config['providers'], dict):
                    errors.append("Field 'providers' must be a dictionary")
            
            elif filename == 'push_config.yaml':
                if 'channels' not in config:
                    errors.append("Missing required field: channels")
                elif not isinstance(config['channels'], dict):
                    errors.append("Field 'channels' must be a dictionary")
            
            elif filename == 'prompt_templates.yaml':
                if 'templates' not in config:
                    errors.append("Missing required field: templates")
                elif not isinstance(config['templates'], list):
                    errors.append("Field 'templates' must be a list")
                else:
                    # Validate each template
                    for idx, template in enumerate(config['templates']):
                        if not isinstance(template, dict):
                            errors.append(f"Template at index {idx} must be a dictionary")
                            continue
                        
                        required_fields = ['data_type', 'template_name', 'system_prompt', 'user_prompt_template']
                        for field in required_fields:
                            if field not in template:
                                errors.append(f"Template at index {idx} missing required field: {field}")
            
            elif filename == 'external_tools.yaml':
                if 'tools' in config and not isinstance(config['tools'], list):
                    errors.append("Field 'tools' must be a list")
            
            # Store validation errors
            self._validation_errors[filename] = errors
            
            if errors:
                logger.warning(f"Validation errors in {filename}: {errors}")
                return False
            
            return True
            
        except Exception as e:
            errors.append(f"Validation exception: {str(e)}")
            self._validation_errors[filename] = errors
            logger.error(f"Validation error for {filename}: {e}")
            return False
    
    def serialize(self, filename: str, config: dict[str, Any]) -> str:
        """
        Serialize configuration to YAML format with proper formatting.
        
        Args:
            filename: Configuration file name
            config: Configuration dictionary
            
        Returns:
            YAML string representation
            
        Validates: Requirements 31.3, 31.7
        """
        try:
            # Use yaml.dump with proper formatting
            yaml_str = yaml.dump(
                config,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                indent=2,
                width=120
            )
            return yaml_str
        except Exception as e:
            logger.error(f"Failed to serialize {filename}: {e}")
            raise ConfigurationError(f"Failed to serialize {filename}: {e}")
    
    def save_config(self, filename: str, config: dict[str, Any]) -> None:
        """
        Save configuration to file with validation.
        
        Args:
            filename: Configuration file name
            config: Configuration dictionary
            
        Raises:
            ConfigurationError: If validation fails or save fails
            
        Validates: Requirements 31.3, 31.4, 31.7
        """
        # Validate before saving
        if not self._validate_config(filename, config):
            errors = self._validation_errors.get(filename, [])
            raise ConfigurationError(
                f"Cannot save invalid configuration for {filename}. Errors: {errors}"
            )
        
        file_path = self.config_dir / filename
        
        try:
            # Serialize to YAML
            yaml_str = self.serialize(filename, config)
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(yaml_str)
            
            # Update cache
            self._configs[filename] = config
            
            logger.info(f"Saved configuration to {filename}")
            
        except Exception as e:
            logger.error(f"Failed to save {filename}: {e}")
            raise ConfigurationError(f"Failed to save {filename}: {e}")
    
    def verify_round_trip(self, filename: str, config: dict[str, Any]) -> bool:
        """
        Verify that parse(serialize(config)) produces equivalent config.
        
        Args:
            filename: Configuration file name
            config: Configuration dictionary
            
        Returns:
            True if round-trip is successful, False otherwise
            
        Validates: Requirements 31.4
        """
        try:
            # Serialize
            yaml_str = self.serialize(filename, config)
            
            # Parse back
            parsed_config = yaml.safe_load(yaml_str)
            
            # Compare (deep equality)
            return parsed_config == config
            
        except Exception as e:
            logger.error(f"Round-trip verification failed for {filename}: {e}")
            return False
    
    async def reload_config(self, filename: str) -> bool:
        """
        Reload configuration from file.
        
        Args:
            filename: Configuration file name
            
        Returns:
            True if reload successful, False otherwise
        """
        try:
            # Load new configuration
            new_config = self._load_config(filename)
            
            # Validate new configuration
            if not self._validate_config(filename, new_config):
                logger.error(
                    f"Configuration validation failed for {filename}. "
                    f"Keeping current configuration. Errors: {self._validation_errors.get(filename, [])}"
                )
                
                # Publish validation failure event
                await self._publish_reload_event(
                    filename,
                    change_type='modified',
                    validation_status='failed',
                    errors=self._validation_errors.get(filename, [])
                )
                
                return False
            
            # Update statistics
            self._reload_count[filename] = self._reload_count.get(filename, 0) + 1
            self._last_reload[filename] = datetime.now()
            
            logger.info(
                f"Successfully reloaded configuration: {filename} "
                f"(reload count: {self._reload_count[filename]})"
            )
            
            # Execute callbacks
            await self._execute_callbacks(filename, new_config)
            
            # Publish reload event
            await self._publish_reload_event(
                filename,
                change_type='modified',
                validation_status='success'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload configuration {filename}: {e}")
            
            # Publish reload failure event
            await self._publish_reload_event(
                filename,
                change_type='modified',
                validation_status='error',
                errors=[str(e)]
            )
            
            return False
    
    async def _execute_callbacks(self, filename: str, config: dict[str, Any]) -> None:
        """
        Execute registered callbacks for configuration reload.
        
        Args:
            filename: Configuration file name
            config: New configuration
        """
        callbacks = self._callbacks.get(filename, [])
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(filename, config)
                else:
                    callback(filename, config)
            except Exception as e:
                logger.error(f"Error executing callback for {filename}: {e}")
    
    async def _publish_reload_event(
        self,
        filename: str,
        change_type: str,
        validation_status: str,
        errors: Optional[list[str]] = None
    ) -> None:
        """
        Publish configuration reload event to event bus.
        
        Args:
            filename: Configuration file name
            change_type: Type of change (added/modified/deleted)
            validation_status: Validation status (success/failed/error)
            errors: List of validation errors (if any)
        """
        if not self.event_bus:
            return
        
        try:
            topic = f"config.reloaded.{filename.replace('.yaml', '')}"
            
            payload = {
                'file_name': filename,
                'change_type': change_type,
                'timestamp': datetime.now().isoformat(),
                'validation_status': validation_status,
                'reload_count': self._reload_count.get(filename, 0)
            }
            
            if errors:
                payload['errors'] = errors
            
            await self.event_bus.publish(topic, payload)
            
            logger.debug(f"Published reload event for {filename} to topic {topic}")
            
        except Exception as e:
            logger.error(f"Failed to publish reload event for {filename}: {e}")
    
    def register_callback(self, filename: str, callback: Callable) -> None:
        """
        Register callback for configuration reload.
        
        Args:
            filename: Configuration file name
            callback: Callback function (sync or async)
        """
        if filename not in self._callbacks:
            self._callbacks[filename] = []
        
        self._callbacks[filename].append(callback)
        logger.debug(f"Registered callback for {filename}")
    
    def unregister_callback(self, filename: str, callback: Callable) -> None:
        """
        Unregister callback for configuration reload.
        
        Args:
            filename: Configuration file name
            callback: Callback function to remove
        """
        if filename in self._callbacks:
            if callback in self._callbacks[filename]:
                self._callbacks[filename].remove(callback)
                logger.debug(f"Unregistered callback for {filename}")
    
    def get_config(self, filename: str) -> Optional[dict[str, Any]]:
        """
        Get cached configuration.
        
        Args:
            filename: Configuration file name
            
        Returns:
            Configuration dictionary or None if not loaded
        """
        return self._configs.get(filename)
    
    def get_statistics(self) -> dict[str, Any]:
        """
        Get configuration manager statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            'watched_files': list(self.watched_files),
            'loaded_configs': list(self._configs.keys()),
            'reload_counts': self._reload_count.copy(),
            'last_reloads': {
                filename: timestamp.isoformat()
                for filename, timestamp in self._last_reload.items()
            },
            'validation_errors': self._validation_errors.copy(),
            'callback_counts': {
                filename: len(callbacks)
                for filename, callbacks in self._callbacks.items()
            }
        }
    
    def add_watched_file(self, filename: str) -> None:
        """
        Add file to watch list.
        
        Args:
            filename: Configuration file name to watch
        """
        if filename not in self.watched_files:
            self.watched_files.add(filename)
            logger.info(f"Added {filename} to watch list")
    
    def remove_watched_file(self, filename: str) -> None:
        """
        Remove file from watch list.
        
        Args:
            filename: Configuration file name to stop watching
        """
        if filename in self.watched_files:
            self.watched_files.remove(filename)
            logger.info(f"Removed {filename} from watch list")
