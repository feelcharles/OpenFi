"""
Enhanced structured logging with trace_id propagation.

Validates: Requirements 24.1, 24.2, 24.3, 24.4, 24.5, 24.6
"""

import sys
import logging
import uuid
import contextvars
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional, Any
import structlog
from pythonjsonlogger import jsonlogger

# Context variable for trace_id propagation
trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'trace_id', default=None
)

def get_trace_id() -> str:
    """
    Get current trace_id from context or generate a new one.
    
    Returns:
        str: Current trace_id or newly generated UUID
    """
    trace_id = trace_id_var.get()
    if trace_id is None:
        trace_id = str(uuid.uuid4())
        trace_id_var.set(trace_id)
    return trace_id

def set_trace_id(trace_id: str) -> None:
    """
    Set trace_id in current context.
    
    Args:
        trace_id: Trace ID to set
    """
    trace_id_var.set(trace_id)

def clear_trace_id() -> None:
    """Clear trace_id from current context."""
    trace_id_var.set(None)

def add_trace_id(logger, method_name, event_dict):
    """
    Structlog processor to add trace_id to all log entries.
    
    Args:
        logger: Logger instance
        method_name: Log method name
        event_dict: Event dictionary
        
    Returns:
        dict: Event dictionary with trace_id added
    """
    event_dict['trace_id'] = get_trace_id()
    return event_dict

def setup_logging_with_trace_id(
    log_level: str = "INFO",
    log_file_path: str = "logs/OpenFi.log",
    log_max_bytes: int = 104857600,  # 100MB
    log_backup_count: int = 10
) -> None:
    """
    Configure structured logging with trace_id support and dual output.
    
    Implements structured logging with fields:
    - timestamp (ISO 8601 format)
    - level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - module (logger name)
    - function (function name)
    - message (log message)
    - context (additional context dict)
    - trace_id (distributed tracing ID)
    
    Outputs to:
    - stdout (for containers) - human-readable format
    - rotating files in logs/ (max 100MB per file) - JSON format
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file_path: Path to log file
        log_max_bytes: Maximum size of each log file in bytes (default 100MB)
        log_backup_count: Number of backup files to keep
        
    Validates: Requirements 24.1, 24.2, 24.3, 24.4, 24.5
    """
    # Create logs directory if it doesn't exist
    log_dir = Path(log_file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
        handlers=[]
    )
    
    # Create JSON formatter for structured logs
    json_formatter = jsonlogger.JsonFormatter(
        fmt="%(timestamp)s %(level)s %(module)s %(funcName)s %(message)s %(trace_id)s",
        rename_fields={
            "levelname": "level",
            "name": "module",
            "asctime": "timestamp",
            "funcName": "function"
        },
        timestamp=True
    )
    
    # Console handler (stdout) - human-readable format for containers
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s [trace_id=%(trace_id)s]",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    
    # File handler (rotating) - JSON format
    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=log_max_bytes,
        backupCount=log_backup_count,
        encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(json_formatter)
    
    # Get root logger and add handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Configure structlog with trace_id processor
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            add_trace_id,  # Add trace_id to all log entries
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

def get_logger(name: str, **context) -> structlog.BoundLogger:
    """
    Get a structured logger instance with optional context.
    
    Args:
        name: Logger name (typically __name__)
        **context: Additional context fields to bind to logger
        
    Returns:
        BoundLogger: Structured logger instance with trace_id support
        
    Example:
        >>> logger = get_logger(__name__, service="fetch_engine")
        >>> logger.info("data_fetched", source="newsapi", count=10)
        # Output includes trace_id automatically
    """
    logger = structlog.get_logger(name)
    if context:
        logger = logger.bind(**context)
    return logger

def log_exception(
    logger: structlog.BoundLogger,
    exception: Exception,
    message: str = "Exception occurred",
    **context
) -> None:
    """
    Log exception with full stack trace, exception type, message, and context.
    
    Args:
        logger: Structured logger instance
        exception: Exception to log
        message: Log message
        **context: Additional context variables
        
    Validates: Requirements 24.6
    """
    logger.error(
        message,
        exc_info=True,
        exception_type=type(exception).__name__,
        exception_message=str(exception),
        **context
    )

class LoggerAdapter:
    """
    Adapter to provide standard logging interface with structured logging backend.
    
    This allows gradual migration from standard logging to structured logging.
    Automatically includes trace_id in all log entries.
    """
    
    def __init__(self, name: str, **context):
        self.logger = get_logger(name, **context)
        self.name = name
    
    def debug(self, message: str, **context):
        """Log debug message with trace_id."""
        self.logger.debug(message, **context)
    
    def info(self, message: str, **context):
        """Log info message with trace_id."""
        self.logger.info(message, **context)
    
    def warning(self, message: str, **context):
        """Log warning message with trace_id."""
        self.logger.warning(message, **context)
    
    def error(self, message: str, **context):
        """Log error message with trace_id."""
        self.logger.error(message, **context)
    
    def critical(self, message: str, **context):
        """Log critical message with trace_id."""
        self.logger.critical(message, **context)
    
    def exception(self, message: str, exc_info: Optional[Exception] = None, **context):
        """
        Log exception with traceback and trace_id.
        
        Args:
            message: Log message
            exc_info: Exception instance (optional, uses sys.exc_info() if None)
            **context: Additional context
        """
        if exc_info:
            log_exception(self.logger, exc_info, message, **context)
        else:
            self.logger.exception(message, **context)
