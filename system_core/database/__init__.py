"""
Database module for OpenFi Lite.

This module provides database models, client, and migration support.
"""

from system_core.database.models import (
    Base,
    User,
    EAProfile,
    PushConfig,
    Trade,
    FetchSource,
    LLMLog,
)
from system_core.database.client import (
    DatabaseClient,
    get_db_client,
    get_db,
    get_session,  # 添加 get_session 导出
    init_db,
    close_db,
)

# Alias for backward compatibility
get_db_manager = get_db_client

__all__ = [
    # Models
    "Base",
    "User",
    "EAProfile",
    "PushConfig",
    "Trade",
    "FetchSource",
    "LLMLog",
    # Client
    "DatabaseClient",
    "get_db_client",
    "get_db_manager",  # 添加别名
    "get_db",
    "get_session",  # 添加到导出列表
    "init_db",
    "close_db",
]
