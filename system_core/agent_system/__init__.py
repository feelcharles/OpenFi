"""
Multi-Agent System Module for OpenFi Lite

This module provides multi-agent management capabilities, allowing users to create
and manage multiple independent intelligent agents with custom configurations,
permissions, asset scopes, trigger conditions, and push settings.

Key Components:
- AgentManager: Agent lifecycle management (CRUD operations)
- AgentExecutor: Agent execution engine for processing trigger events
- ConfigManager: Configuration management with versioning and caching
- AgentIsolator: Data isolation between agents

Integration:
- Reuses existing database, auth, event_bus, monitoring modules
- Integrates with ai_engine, factor_system, execution_engine, user_center
"""

from system_core.agent_system.manager import AgentManager
from system_core.agent_system.executor import AgentExecutor

__all__ = [
    "AgentManager",
    "AgentExecutor",
]
