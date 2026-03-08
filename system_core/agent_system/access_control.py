"""
Agent Access Control Decorators and Middleware

Provides decorators and middleware to enforce agent data access isolation.
Ensures agents can only access data they are authorized to see.

Requirements: 43.1, 43.2, 43.3
"""

import asyncio
import functools
import logging
from typing import Any, Callable, Optional
from uuid import UUID

from system_core.agent_system.isolator import AgentIsolator
from system_core.core.exceptions import PermissionError as HBPermissionError

logger = logging.getLogger(__name__)

def require_agent_isolation(
    resource_type: str,
    resource_id_param: str = "resource_id",
    agent_id_param: str = "agent_id"
):
    """
    Decorator to enforce agent data access isolation.
    
    Validates that an agent has permission to access a specific resource
    before allowing the function to execute.
    
    Args:
        resource_type: Type of resource being accessed (e.g., "trade", "signal", "config")
        resource_id_param: Name of parameter containing resource ID
        agent_id_param: Name of parameter containing agent ID
    
    Usage:
        @require_agent_isolation("trade", resource_id_param="trade_id")
        async def get_trade(agent_id: str, trade_id: str):
            # This will only execute if agent has access to the trade
            pass
    
    Raises:
        PermissionError: If agent does not have access to resource
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract agent_id and resource_id from parameters
            agent_id = kwargs.get(agent_id_param)
            resource_id = kwargs.get(resource_id_param)
            
            if agent_id is None:
                raise ValueError(f"Missing required parameter: {agent_id_param}")
            
            if resource_id is None:
                raise ValueError(f"Missing required parameter: {resource_id_param}")
            
            # Validate access
            isolator = AgentIsolator()
            
            is_allowed = await isolator.validate_data_access(
                agent_id=agent_id,
                resource_type=resource_type,
                resource_id=resource_id
            )
            
            if not is_allowed:
                logger.warning(
                    f"Access denied: Agent {agent_id} attempted to access "
                    f"{resource_type}:{resource_id}"
                )
                raise HBPermissionError(
                    f"Agent {agent_id} does not have access to {resource_type}:{resource_id}"
                )
            
            # Access granted, execute function
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we need to run async validation
            import asyncio
            
            agent_id = kwargs.get(agent_id_param)
            resource_id = kwargs.get(resource_id_param)
            
            if agent_id is None:
                raise ValueError(f"Missing required parameter: {agent_id_param}")
            
            if resource_id is None:
                raise ValueError(f"Missing required parameter: {resource_id_param}")
            
            # Validate access
            isolator = AgentIsolator()
            
            # Run async validation in sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            is_allowed = loop.run_until_complete(
                isolator.validate_data_access(
                    agent_id=agent_id,
                    resource_type=resource_type,
                    resource_id=resource_id
                )
            )
            
            if not is_allowed:
                logger.warning(
                    f"Access denied: Agent {agent_id} attempted to access "
                    f"{resource_type}:{resource_id}"
                )
                raise HBPermissionError(
                    f"Agent {agent_id} does not have access to {resource_type}:{resource_id}"
                )
            
            # Access granted, execute function
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def require_agent_permission(
    permission: str,
    agent_id_param: str = "agent_id"
):
    """
    Decorator to check if agent has a specific permission.
    
    Args:
        permission: Permission to check (e.g., "info_retrieval", "ai_analysis")
        agent_id_param: Name of parameter containing agent ID
    
    Usage:
        @require_agent_permission("ai_analysis")
        async def analyze_data(agent_id: str, data: dict):
            # This will only execute if agent has ai_analysis permission
            pass
    
    Raises:
        PermissionError: If agent does not have the required permission
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            agent_id = kwargs.get(agent_id_param)
            
            if agent_id is None:
                raise ValueError(f"Missing required parameter: {agent_id_param}")
            
            # Check permission
            isolator = AgentIsolator()
            has_permission = await isolator.check_agent_permission(
                agent_id=agent_id,
                permission=permission
            )
            
            if not has_permission:
                logger.warning(
                    f"Permission denied: Agent {agent_id} lacks permission '{permission}'"
                )
                raise HBPermissionError(
                    f"Agent {agent_id} does not have permission: {permission}"
                )
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            import asyncio
            
            agent_id = kwargs.get(agent_id_param)
            
            if agent_id is None:
                raise ValueError(f"Missing required parameter: {agent_id_param}")
            
            isolator = AgentIsolator()
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            has_permission = loop.run_until_complete(
                isolator.check_agent_permission(
                    agent_id=agent_id,
                    permission=permission
                )
            )
            
            if not has_permission:
                logger.warning(
                    f"Permission denied: Agent {agent_id} lacks permission '{permission}'"
                )
                raise HBPermissionError(
                    f"Agent {agent_id} does not have permission: {permission}"
                )
            
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def require_agent_asset_access(
    symbol_param: str = "symbol",
    agent_id_param: str = "agent_id"
):
    """
    Decorator to check if agent has access to a specific trading symbol.
    
    Args:
        symbol_param: Name of parameter containing symbol
        agent_id_param: Name of parameter containing agent ID
    
    Usage:
        @require_agent_asset_access(symbol_param="symbol")
        async def get_market_data(agent_id: str, symbol: str):
            # This will only execute if agent is configured to monitor this symbol
            pass
    
    Raises:
        PermissionError: If agent does not have access to the symbol
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            agent_id = kwargs.get(agent_id_param)
            symbol = kwargs.get(symbol_param)
            
            if agent_id is None:
                raise ValueError(f"Missing required parameter: {agent_id_param}")
            
            if symbol is None:
                raise ValueError(f"Missing required parameter: {symbol_param}")
            
            # Check asset access
            isolator = AgentIsolator()
            has_access = await isolator.check_agent_asset_access(
                agent_id=agent_id,
                symbol=symbol
            )
            
            if not has_access:
                logger.warning(
                    f"Asset access denied: Agent {agent_id} cannot access symbol {symbol}"
                )
                raise HBPermissionError(
                    f"Agent {agent_id} does not have access to symbol: {symbol}"
                )
            
            return await func(*args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            import asyncio
            
            agent_id = kwargs.get(agent_id_param)
            symbol = kwargs.get(symbol_param)
            
            if agent_id is None:
                raise ValueError(f"Missing required parameter: {agent_id_param}")
            
            if symbol is None:
                raise ValueError(f"Missing required parameter: {symbol_param}")
            
            isolator = AgentIsolator()
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            has_access = loop.run_until_complete(
                isolator.check_agent_asset_access(
                    agent_id=agent_id,
                    symbol=symbol
                )
            )
            
            if not has_access:
                logger.warning(
                    f"Asset access denied: Agent {agent_id} cannot access symbol {symbol}"
                )
                raise HBPermissionError(
                    f"Agent {agent_id} does not have access to symbol: {symbol}"
                )
            
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

class AgentAccessMiddleware:
    """
    Middleware for enforcing agent access control in web APIs.
    
    Usage:
        from fastapi import FastAPI
        
        app = FastAPI()
        app.add_middleware(AgentAccessMiddleware)
    """
    
    def __init__(self, app):
        """Initialize middleware."""
        self.app = app
        self.isolator = AgentIsolator()
    
    async def __call__(self, scope, receive, send):
        """Process request with access control."""
        if scope["type"] == "http":
            # Extract agent_id from headers or query params
            headers = dict(scope.get("headers", []))
            agent_id = headers.get(b"x-agent-id")
            
            if agent_id:
                agent_id = agent_id.decode("utf-8")
                
                # Validate agent exists and is active
                is_valid = await self.isolator.validate_agent_status(agent_id)
                
                if not is_valid:
                    # Return 403 Forbidden
                    await send({
                        "type": "http.response.start",
                        "status": 403,
                        "headers": [[b"content-type", b"application/json"]],
                    })
                    await send({
                        "type": "http.response.body",
                        "body": b'{"error": "Agent not authorized"}',
                    })
                    return
        
        # Continue to next middleware/handler
        await self.app(scope, receive, send)

__all__ = [
    'require_agent_isolation',
    'require_agent_permission',
    'require_agent_asset_access',
    'AgentAccessMiddleware',
]

