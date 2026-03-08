"""
Structured logging configuration.

Validates: Requirements 14.1, 14.2, 14.3
"""

import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
import structlog
from pythonjsonlogger import jsonlogger

def setup_logging(
    log_level: str = "INFO",
    log_file_path: str = "logs/OpenFi.log",
    log_max_bytes: int = 104857600,  # 100MB
    log_backup_count: int = 10
) -> None:
    """
    Configure structured logging with dual output (stdout and rotating file).
    
    Implements structured logging with fields: timestamp, level, module, message, context
    Outputs to both stdout and rotating log files with maximum size of 100MB per file.
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file_path: Path to log file
        log_max_bytes: Maximum size of each log file in bytes
        log_backup_count: Number of backup files to keep
        
    Validates: Requirements 14.1, 14.2, 14.3
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
        fmt="%(timestamp)s %(level)s %(module)s %(message)s %(context)s",
        rename_fields={
            "levelname": "level",
            "name": "module",
            "asctime": "timestamp"
        }
    )
    
    # Console handler (stdout) - human-readable format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
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
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
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
        BoundLogger: Structured logger instance
        
    Example:
        >>> logger = get_logger(__name__, service="fetch_engine")
        >>> logger.info("data_fetched", source="newsapi", count=10)
    """
    logger = structlog.get_logger(name)
    if context:
        logger = logger.bind(**context)
    return logger

class LoggerAdapter:
    """
    Adapter to provide standard logging interface with structured logging backend.
    
    This allows gradual migration from standard logging to structured logging.
    """
    
    def __init__(self, name: str, **context):
        self.logger = get_logger(name, **context)
        self.name = name
    
    def debug(self, message: str, **context):
        """Log debug message."""
        self.logger.debug(message, **context)
    
    def info(self, message: str, **context):
        """Log info message."""
        self.logger.info(message, **context)
    
    def warning(self, message: str, **context):
        """Log warning message."""
        self.logger.warning(message, **context)
    
    def error(self, message: str, **context):
        """Log error message."""
        self.logger.error(message, **context)
    
    def critical(self, message: str, **context):
        """Log critical message."""
        self.logger.critical(message, **context)
    
    def exception(self, message: str, **context):
        """Log exception with traceback."""
        self.logger.exception(message, **context)
