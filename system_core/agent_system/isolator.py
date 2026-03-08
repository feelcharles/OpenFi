"""
Agent Isolator

Implements data isolation between agents to ensure each agent can only access
its own data and resources.
"""

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from contextlib import asynccontextmanager

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.database.client import DatabaseClient, get_db_client

logger = logging.getLogger(__name__)

class AgentIsolator:
    """
    Agent Isolator for enforcing data isolation between agents.
    
    Responsibilities:
    - Create isolated execution contexts with agent_id
    - Validate data access permissions
    - Audit all access attempts
    - Automatically add agent_id filters to database queries
    - Implement cache key prefixing with agent_id
    
    **Validates: Requirements 7.1-7.9**
    """
    
    def __init__(
        self,
        db_client: Optional[DatabaseClient] = None,
    ):
        """
        Initialize Agent Isolator.
        
        Args:
            db_client: Database client instance (defaults to global client)
        """
        self.db_client = db_client or get_db_client()
        
        # Access audit log (in-memory for now, should be persisted)
        self._access_log: list[dict[str, Any]] = []
        
        logger.info("AgentIsolator initialized")
    
    @asynccontextmanager
    async def create_isolated_context(
        self,
        agent_id: UUID,
        operation: str,
        resource_type: Optional[str] = None,
    ):
        """
        Create an isolated execution context for an agent.
        
        This context manager ensures that all operations within the context
        are scoped to the specified agent_id.
        
        Args:
            agent_id: Agent UUID
            operation: Operation being performed (e.g., "read", "write", "delete")
            resource_type: Optional resource type being accessed
            
        Yields:
            Isolated context dictionary with agent_id and metadata
            
        **Validates: Requirements 7.1, 7.2**
        
        Example:
            async with isolator.create_isolated_context(agent_id, "read", "metrics") as ctx:
                # All operations here are scoped to agent_id
                metrics = await fetch_metrics(ctx["agent_id"])
        """
        context = {
            "agent_id": agent_id,
            "operation": operation,
            "resource_type": resource_type,
            "timestamp": datetime.utcnow(),
        }
        
        # Audit access attempt
        await self.audit_access_attempt(
            agent_id=agent_id,
            operation=operation,
            resource_type=resource_type,
            status="started",
        )
        
        try:
            logger.debug(
                f"Created isolated context for agent {agent_id}: "
                f"operation={operation}, resource_type={resource_type}"
            )
            yield context
            
            # Audit successful completion
            await self.audit_access_attempt(
                agent_id=agent_id,
                operation=operation,
                resource_type=resource_type,
                status="completed",
            )
            
        except Exception as e:
            # Audit failure
            await self.audit_access_attempt(
                agent_id=agent_id,
                operation=operation,
                resource_type=resource_type,
                status="failed",
                error=str(e),
            )
            raise
    
    async def validate_data_access(
        self,
        agent_id: UUID,
        resource_type: str,
        resource_id: Optional[UUID] = None,
        operation: str = "read",
    ) -> bool:
        """
        Validate if an agent has permission to access a resource.
        
        Args:
            agent_id: Agent UUID requesting access
            resource_type: Type of resource (e.g., "config", "metrics", "logs")
            resource_id: Optional specific resource ID
            operation: Operation type (read, write, delete)
            
        Returns:
            True if access is allowed, False otherwise
            
        **Validates: Requirements 7.3, 7.4**
        """
        # For now, agents can only access their own resources
        # In the future, this could be extended with more complex ACL rules
        
        # Audit the access validation attempt
        await self.audit_access_attempt(
            agent_id=agent_id,
            operation=f"validate_{operation}",
            resource_type=resource_type,
            resource_id=resource_id,
            status="validated",
        )
        
        # Basic rule: agents can access their own resources
        # If resource_id is provided, we would need to check if it belongs to agent_id
        # This would require querying the database to verify ownership
        
        if resource_id:
            # Check if resource belongs to agent
            is_owner = await self._check_resource_ownership(
                agent_id=agent_id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
            
            if not is_owner:
                logger.warning(
                    f"Agent {agent_id} attempted to access {resource_type} "
                    f"{resource_id} without ownership"
                )
                return False
        
        return True
    
    async def audit_access_attempt(
        self,
        agent_id: UUID,
        operation: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        status: str = "attempted",
        error: Optional[str] = None,
    ) -> None:
        """
        Record an access attempt for auditing purposes.
        
        Args:
            agent_id: Agent UUID
            operation: Operation being performed
            resource_type: Optional resource type
            resource_id: Optional resource ID
            status: Status of the attempt (attempted, completed, failed, denied)
            error: Optional error message
            
        **Validates: Requirements 7.5, 7.6**
        """
        audit_entry = {
            "agent_id": str(agent_id),
            "operation": operation,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "status": status,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Store in memory (in production, this should be persisted to database)
        self._access_log.append(audit_entry)
        
        # Log to application logger
        log_level = logging.WARNING if status == "failed" else logging.INFO
        logger.log(
            log_level,
            f"Access audit: agent={agent_id}, operation={operation}, "
            f"resource_type={resource_type}, status={status}"
        )
        
        # In production, persist to database
        try:
            async with self.db_client.session() as session:
                from system_core.database.models import AgentLog as AgentLogModel
                
                log = AgentLogModel(
                    agent_id=agent_id,
                    log_level="INFO" if status == "completed" else "WARNING",
                    message=f"Access {status}: {operation} on {resource_type}",
                    context=audit_entry,
                    timestamp=datetime.utcnow(),
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to persist audit log: {e}")
    
    def add_agent_filter(
        self,
        query,
        agent_id: UUID,
        model_class,
    ):
        """
        Add agent_id filter to a SQLAlchemy query.
        
        This ensures that queries automatically filter by agent_id.
        
        Args:
            query: SQLAlchemy query object
            agent_id: Agent UUID to filter by
            model_class: SQLAlchemy model class
            
        Returns:
            Modified query with agent_id filter
            
        **Validates: Requirements 7.7**
        
        Example:
            query = select(AgentMetric)
            query = isolator.add_agent_filter(query, agent_id, AgentMetric)
            # Query now includes WHERE agent_id = :agent_id
        """
        if hasattr(model_class, 'agent_id'):
            query = query.where(model_class.agent_id == agent_id)
        else:
            logger.warning(
                f"Model {model_class.__name__} does not have agent_id field, "
                f"cannot apply isolation filter"
            )
        
        return query
    
    def get_cache_key(
        self,
        agent_id: UUID,
        key: str,
    ) -> str:
        """
        Generate a cache key with agent_id prefix.
        
        This ensures cache isolation between agents.
        
        Args:
            agent_id: Agent UUID
            key: Base cache key
            
        Returns:
            Prefixed cache key
            
        **Validates: Requirements 7.8**
        
        Example:
            cache_key = isolator.get_cache_key(agent_id, "config")
            # Returns: "agent:{agent_id}:config"
        """
        return f"agent:{agent_id}:{key}"
    
    async def get_access_log(
        self,
        agent_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get access audit log entries.
        
        Args:
            agent_id: Optional agent UUID to filter by
            limit: Maximum number of entries to return
            
        Returns:
            List of audit log entries
            
        **Validates: Requirements 7.9**
        """
        if agent_id:
            filtered_log = [
                entry for entry in self._access_log
                if entry["agent_id"] == str(agent_id)
            ]
        else:
            filtered_log = self._access_log
        
        # Return most recent entries
        return filtered_log[-limit:]
    
    async def _check_resource_ownership(
        self,
        agent_id: UUID,
        resource_type: str,
        resource_id: UUID,
    ) -> bool:
        """
        Check if a resource belongs to an agent.
        
        Args:
            agent_id: Agent UUID
            resource_type: Resource type
            resource_id: Resource ID
            
        Returns:
            True if agent owns the resource, False otherwise
        """
        try:
            async with self.db_client.session() as session:
                # Map resource types to models
                from system_core.database.models import (
                    AgentConfig as AgentConfigModel,
                    AgentMetric as AgentMetricModel,
                    AgentLog as AgentLogModel,
                    AgentAsset as AgentAssetModel,
                    AgentTrigger as AgentTriggerModel,
                    AgentPushConfig as AgentPushConfigModel,
                    AgentBotConnection as AgentBotConnectionModel,
                )
                
                model_map = {
                    "config": AgentConfigModel,
                    "metrics": AgentMetricModel,
                    "logs": AgentLogModel,
                    "assets": AgentAssetModel,
                    "triggers": AgentTriggerModel,
                    "push_config": AgentPushConfigModel,
                    "bot_connections": AgentBotConnectionModel,
                }
                
                model_class = model_map.get(resource_type)
                if not model_class:
                    logger.warning(f"Unknown resource type: {resource_type}")
                    return False
                
                # Query to check ownership
                query = select(model_class).where(
                    and_(
                        model_class.id == resource_id,
                        model_class.agent_id == agent_id,
                    )
                )
                
                result = await session.execute(query)
                resource = result.scalar_one_or_none()
                
                return resource is not None
                
        except Exception as e:
            logger.error(f"Failed to check resource ownership: {e}")
            return False

    async def check_agent_permission(
        self,
        agent_id: UUID,
        permission: str
    ) -> bool:
        """
        Check if an agent has a specific permission.
        
        Args:
            agent_id: Agent UUID
            permission: Permission to check (e.g., "info_retrieval", "ai_analysis")
        
        Returns:
            True if agent has the permission, False otherwise
        """
        try:
            async with self.db_client.session() as session:
                from system_core.database.models import Agent, AgentConfig
                
                # Get agent's latest config
                query = (
                    select(AgentConfig)
                    .where(AgentConfig.agent_id == agent_id)
                    .order_by(AgentConfig.version.desc())
                    .limit(1)
                )
                
                result = await session.execute(query)
                config = result.scalar_one_or_none()
                
                if not config:
                    logger.warning(f"No config found for agent {agent_id}")
                    return False
                
                # Check permissions in config
                config_json = config.config_json or {}
                permissions = config_json.get('permissions', {})
                
                # Check if permission exists and is granted
                permission_value = permissions.get(permission)
                
                if permission_value in ['full_access', 'enabled', True]:
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Failed to check agent permission: {e}")
            return False
    
    async def check_agent_asset_access(
        self,
        agent_id: UUID,
        symbol: str
    ) -> bool:
        """
        Check if an agent has access to a specific trading symbol.
        
        Args:
            agent_id: Agent UUID
            symbol: Trading symbol (e.g., "XAUUSD", "EURUSD")
        
        Returns:
            True if agent has access to the symbol, False otherwise
        """
        try:
            async with self.db_client.session() as session:
                from system_core.database.models import AgentAsset
                
                # Check if agent has this symbol in their asset portfolio
                query = select(AgentAsset).where(
                    and_(
                        AgentAsset.agent_id == agent_id,
                        AgentAsset.symbol == symbol
                    )
                )
                
                result = await session.execute(query)
                asset = result.scalar_one_or_none()
                
                return asset is not None
                
        except Exception as e:
            logger.error(f"Failed to check agent asset access: {e}")
            return False
    
    async def validate_agent_status(
        self,
        agent_id: UUID
    ) -> bool:
        """
        Validate that an agent exists and is active.
        
        Args:
            agent_id: Agent UUID
        
        Returns:
            True if agent is valid and active, False otherwise
        """
        try:
            async with self.db_client.session() as session:
                from system_core.database.models import Agent
                
                query = select(Agent).where(Agent.id == agent_id)
                result = await session.execute(query)
                agent = result.scalar_one_or_none()
                
                if not agent:
                    return False
                
                # Check if agent is active
                return agent.status == 'active'
                
        except Exception as e:
            logger.error(f"Failed to validate agent status: {e}")
            return False
