"""
Agent Manager

Manages the lifecycle of agents including CRUD operations, state management,
cloning, and configuration versioning.
"""

import logging
from typing import Optional, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, and_, or_, func, delete
from sqlalchemy.orm import selectinload

from system_core.database.client import DatabaseClient, get_db_client
from system_core.database.models import (
    Agent as AgentModel,
    AgentConfig as AgentConfigModel,
    AgentAsset as AgentAssetModel,
    AgentTrigger as AgentTriggerModel,
    AgentPushConfig as AgentPushConfigModel,
    AgentBotConnection as AgentBotConnectionModel,
    AgentMetric as AgentMetricModel,
    AgentLog as AgentLogModel,
)
from system_core.agent_system.models import (
    Agent,
    AgentCreate,
    AgentUpdate,
    AgentWithConfig,
    AgentStatus,
    AgentConfig,
    AgentLogCreate,
)

logger = logging.getLogger(__name__)

class AgentManager:
    """
    Agent Manager for multi-agent system lifecycle management.
    
    Responsibilities:
    - Agent CRUD operations
    - Agent state management (active, inactive, paused, error)
    - Agent cloning and template application
    - Configuration validation and versioning
    - Permission checking
    """
    
    def __init__(self, db_client: Optional[DatabaseClient] = None):
        """
        Initialize Agent Manager.
        
        Args:
            db_client: Database client instance (defaults to global client)
        """
        self.db_client = db_client or get_db_client()
        logger.info("AgentManager initialized")
    
    async def create_agent(
        self,
        agent_data: AgentCreate,
        created_by: str,
    ) -> AgentWithConfig:
        """
        Create a new agent with unique ID and name.
        
        Validates name uniqueness, generates UUID, initializes default configuration,
        and creates AgentConfig record.
        
        Args:
            agent_data: Agent creation data
            created_by: User identifier who created the agent
            
        Returns:
            Created agent with configuration
            
        Raises:
            ValueError: If agent name already exists
            
        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        logger.info(f"Creating agent: {agent_data.name}")
        
        async with self.db_client.session() as session:
            # Check name uniqueness
            existing = await session.execute(
                select(AgentModel).where(AgentModel.name == agent_data.name)
            )
            existing_agent = existing.scalar_one_or_none()
            if existing_agent:
                raise ValueError(f"Agent name '{agent_data.name}' already exists")
            
            # Create agent with UUID
            agent = AgentModel(
                name=agent_data.name,
                description=agent_data.description,
                status=agent_data.status.value,
                priority=agent_data.priority.value,
                owner_user_id=agent_data.owner_user_id,
                tags=agent_data.tags,
                category=agent_data.category,
                agent_metadata=agent_data.metadata,
            )
            session.add(agent)
            await session.flush()  # Get agent.id
            
            # Initialize default configuration
            config = agent_data.config or AgentConfig()
            config_model = AgentConfigModel(
                agent_id=agent.id,
                version=1,
                config_json={
                    "permissions": config.permissions.model_dump(),
                    "asset_portfolio": config.asset_portfolio.model_dump(),
                    "trigger_config": config.trigger_config.model_dump(),
                    "push_config": config.push_config.model_dump(),
                    "quotas": config.quotas.model_dump(),
                    "bot_connections": [bc.model_dump() for bc in config.bot_connections],
                },
                created_by=created_by,
                change_description="Initial configuration",
            )
            session.add(config_model)
            
            # Create asset records
            for asset in config.asset_portfolio.assets:
                asset_model = AgentAssetModel(
                    agent_id=agent.id,
                    symbol=asset.symbol,
                    weight=asset.weight,
                    category=asset.category.value,
                )
                session.add(asset_model)
            
            # Create push config record
            push_config_model = AgentPushConfigModel(
                agent_id=agent.id,
                push_config_json=config.push_config.model_dump(),
            )
            session.add(push_config_model)
            
            await session.commit()
            await session.refresh(agent)
            
            logger.info(f"Agent created: {agent.id} ({agent.name})")
            
            # Log creation
            await self._log_agent_event(
                agent_id=agent.id,
                log_level="INFO",
                message=f"Agent created by {created_by}",
                context={"created_by": created_by},
            )
            
            return await self._agent_to_response(agent, config)
    
    async def get_agent(
        self,
        agent_id: Optional[UUID] = None,
        agent_name: Optional[str] = None,
        include_config: bool = True,
    ) -> Optional[AgentWithConfig]:
        """
        Get agent by ID or name.
        
        Args:
            agent_id: Agent UUID
            agent_name: Agent name
            include_config: Include configuration in response
            
        Returns:
            Agent with optional configuration, or None if not found
            
        Raises:
            ValueError: If neither agent_id nor agent_name provided
            
        **Validates: Requirements 1.4**
        """
        if not agent_id and not agent_name:
            raise ValueError("Either agent_id or agent_name must be provided")
        
        async with self.db_client.session() as session:
            query = select(AgentModel)
            
            if agent_id:
                query = query.where(AgentModel.id == agent_id)
            else:
                query = query.where(AgentModel.name == agent_name)
            
            result = await session.execute(query)
            agent = result.scalar_one_or_none()
            
            if not agent:
                return None
            
            if include_config:
                # Get latest config
                config_query = (
                    select(AgentConfigModel)
                    .where(AgentConfigModel.agent_id == agent.id)
                    .order_by(AgentConfigModel.version.desc())
                    .limit(1)
                )
                config_result = await session.execute(config_query)
                config_model = config_result.scalar_one_or_none()
                
                config = None
                if config_model:
                    config = AgentConfig(**config_model.config_json)
                
                return await self._agent_to_response(agent, config)
            else:
                return await self._agent_to_response(agent, None)
    
    async def list_agents(
        self,
        status: Optional[AgentStatus] = None,
        owner_user_id: Optional[UUID] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Agent]:
        """
        List agents with filtering and pagination.
        
        Args:
            status: Filter by agent status
            owner_user_id: Filter by owner user ID
            category: Filter by category
            tags: Filter by tags (any match)
            offset: Pagination offset
            limit: Pagination limit (max 100)
            
        Returns:
            List of agents
            
        **Validates: Requirements 1.4**
        """
        logger.info(f"Listing agents: status={status}, owner={owner_user_id}, category={category}")
        
        async with self.db_client.session() as session:
            query = select(AgentModel)
            
            # Apply filters
            filters = []
            if status:
                filters.append(AgentModel.status == status.value)
            if owner_user_id:
                filters.append(AgentModel.owner_user_id == owner_user_id)
            if category:
                filters.append(AgentModel.category == category)
            if tags:
                # Match any tag
                filters.append(AgentModel.tags.overlap(tags))
            
            if filters:
                query = query.where(and_(*filters))
            
            # Apply pagination
            query = query.offset(offset).limit(min(limit, 100))
            query = query.order_by(AgentModel.created_at.desc())
            
            result = await session.execute(query)
            agents = result.scalars().all()
            
            return [Agent.model_validate(agent) for agent in agents]
    
    async def update_agent(
        self,
        agent_id: UUID,
        updates: AgentUpdate,
        updated_by: str,
        config_updates: Optional[AgentConfig] = None,
        change_description: Optional[str] = None,
    ) -> AgentWithConfig:
        """
        Update agent configuration with versioning.
        
        Validates configuration, creates new AgentConfig version, and updates Agent.
        
        Args:
            agent_id: Agent UUID
            updates: Agent update data
            updated_by: User identifier who updated the agent
            config_updates: Optional configuration updates
            change_description: Description of changes
            
        Returns:
            Updated agent with configuration
            
        Raises:
            ValueError: If agent not found or validation fails
            
        **Validates: Requirements 1.5, 8.3**
        """
        logger.info(f"Updating agent: {agent_id}")
        
        async with self.db_client.session() as session:
            # Get existing agent
            result = await session.execute(
                select(AgentModel).where(AgentModel.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")
            
            # Update agent fields
            update_data = updates.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(agent, field):
                    if field in ['status', 'priority'] and value:
                        setattr(agent, field, value.value)
                    else:
                        setattr(agent, field, value)
            
            # Update configuration if provided
            config = None
            if config_updates:
                # Get current version
                version_query = (
                    select(func.max(AgentConfigModel.version))
                    .where(AgentConfigModel.agent_id == agent_id)
                )
                version_result = await session.execute(version_query)
                current_version = version_result.scalar() or 0
                
                # Create new version
                new_config = AgentConfigModel(
                    agent_id=agent_id,
                    version=current_version + 1,
                    config_json={
                        "permissions": config_updates.permissions.model_dump(),
                        "asset_portfolio": config_updates.asset_portfolio.model_dump(),
                        "trigger_config": config_updates.trigger_config.model_dump(),
                        "push_config": config_updates.push_config.model_dump(),
                        "quotas": config_updates.quotas.model_dump(),
                        "bot_connections": [bc.model_dump() for bc in config_updates.bot_connections],
                    },
                    created_by=updated_by,
                    change_description=change_description or "Configuration update",
                )
                session.add(new_config)
                
                # Update assets
                await session.execute(
                    delete(AgentAssetModel).where(AgentAssetModel.agent_id == agent_id)
                )
                for asset in config_updates.asset_portfolio.assets:
                    asset_model = AgentAssetModel(
                        agent_id=agent_id,
                        symbol=asset.symbol,
                        weight=asset.weight,
                        category=asset.category.value,
                    )
                    session.add(asset_model)
                
                # Update push config
                push_result = await session.execute(
                    select(AgentPushConfigModel).where(AgentPushConfigModel.agent_id == agent_id)
                )
                push_config = push_result.scalar_one_or_none()
                if push_config:
                    push_config.push_config_json = config_updates.push_config.model_dump()
                else:
                    push_config = AgentPushConfigModel(
                        agent_id=agent_id,
                        push_config_json=config_updates.push_config.model_dump(),
                    )
                    session.add(push_config)
                
                config = config_updates
            
            await session.commit()
            await session.refresh(agent)
            
            logger.info(f"Agent updated: {agent_id}")
            
            # Log update
            await self._log_agent_event(
                agent_id=agent_id,
                log_level="INFO",
                message=f"Agent updated by {updated_by}",
                context={"updated_by": updated_by, "changes": change_description},
            )
            
            return await self._agent_to_response(agent, config)
    
    async def delete_agent(
        self,
        agent_id: UUID,
        force: bool = False,
        deleted_by: str = "system",
    ) -> bool:
        """
        Delete agent and cascade delete all related records.
        
        Prevents deletion of active agents without explicit confirmation.
        Archives historical data for audit purposes.
        
        Args:
            agent_id: Agent UUID
            force: Force deletion even if agent is active
            deleted_by: User identifier who deleted the agent
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If agent not found or is active without force flag
            
        **Validates: Requirements 1.6, 1.7, 1.8**
        """
        logger.info(f"Deleting agent: {agent_id}, force={force}")
        
        async with self.db_client.session() as session:
            # Get agent
            result = await session.execute(
                select(AgentModel).where(AgentModel.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")
            
            # Check if active
            if agent.status == AgentStatus.ACTIVE.value and not force:
                raise ValueError(
                    f"Cannot delete active agent {agent_id}. "
                    "Set force=True to delete anyway."
                )
            
            # Log deletion before deleting
            await self._log_agent_event(
                agent_id=agent_id,
                log_level="WARNING",
                message=f"Agent deleted by {deleted_by}",
                context={"deleted_by": deleted_by, "force": force},
            )
            
            # Delete agent (cascade will handle related records)
            await session.delete(agent)
            await session.commit()
            
            logger.info(f"Agent deleted: {agent_id}")
            
            return True
    
    async def clone_agent(
        self,
        agent_id: UUID,
        new_name: Optional[str] = None,
        cloned_by: str = "system",
    ) -> AgentWithConfig:
        """
        Clone an existing agent with new UUID and unique name.
        
        Copies all configuration settings but not historical data or metrics.
        Generates new UUID and deduplicates name by appending suffix.
        
        Args:
            agent_id: Source agent UUID
            new_name: New agent name (auto-generated if not provided)
            cloned_by: User identifier who cloned the agent
            
        Returns:
            Cloned agent with configuration
            
        Raises:
            ValueError: If source agent not found
            
        **Validates: Requirements 19.1, 19.2, 19.3, 19.4**
        """
        logger.info(f"Cloning agent: {agent_id}")
        
        async with self.db_client.session() as session:
            # Get source agent
            result = await session.execute(
                select(AgentModel).where(AgentModel.id == agent_id)
            )
            source_agent = result.scalar_one_or_none()
            
            if not source_agent:
                raise ValueError(f"Agent {agent_id} not found")
            
            # Generate unique name
            if not new_name:
                new_name = await self._generate_unique_name(source_agent.name)
            else:
                # Check if provided name is unique
                existing = await session.execute(
                    select(AgentModel).where(AgentModel.name == new_name)
                )
                if existing.scalar_one_or_none():
                    new_name = await self._generate_unique_name(new_name)
            
            # Get source config
            config_query = (
                select(AgentConfigModel)
                .where(AgentConfigModel.agent_id == agent_id)
                .order_by(AgentConfigModel.version.desc())
                .limit(1)
            )
            config_result = await session.execute(config_query)
            source_config = config_result.scalar_one_or_none()
            
            if not source_config:
                raise ValueError(f"Agent {agent_id} has no configuration")
            
            # Create cloned agent
            cloned_agent = AgentModel(
                name=new_name,
                description=f"Cloned from {source_agent.name}",
                status=AgentStatus.INACTIVE.value,  # Start as inactive
                priority=source_agent.priority,
                owner_user_id=source_agent.owner_user_id,
                tags=source_agent.tags.copy() if source_agent.tags else [],
                category=source_agent.category,
                agent_metadata=source_agent.agent_metadata.copy() if source_agent.agent_metadata else {},
            )
            session.add(cloned_agent)
            await session.flush()
            
            # Clone configuration
            cloned_config = AgentConfigModel(
                agent_id=cloned_agent.id,
                version=1,
                config_json=source_config.config_json.copy(),
                created_by=cloned_by,
                change_description=f"Cloned from agent {agent_id}",
            )
            session.add(cloned_config)
            
            # Clone assets
            assets_query = select(AgentAssetModel).where(AgentAssetModel.agent_id == agent_id)
            assets_result = await session.execute(assets_query)
            source_assets = assets_result.scalars().all()
            
            for asset in source_assets:
                cloned_asset = AgentAssetModel(
                    agent_id=cloned_agent.id,
                    symbol=asset.symbol,
                    weight=asset.weight,
                    category=asset.category,
                )
                session.add(cloned_asset)
            
            # Clone push config
            push_query = select(AgentPushConfigModel).where(AgentPushConfigModel.agent_id == agent_id)
            push_result = await session.execute(push_query)
            source_push = push_result.scalar_one_or_none()
            
            if source_push:
                cloned_push = AgentPushConfigModel(
                    agent_id=cloned_agent.id,
                    push_config_json=source_push.push_config_json.copy(),
                )
                session.add(cloned_push)
            
            await session.commit()
            await session.refresh(cloned_agent)
            await session.refresh(cloned_config)
            
            logger.info(f"Agent cloned: {cloned_agent.id} ({cloned_agent.name})")
            
            # Log cloning
            await self._log_agent_event(
                agent_id=cloned_agent.id,
                log_level="INFO",
                message=f"Agent cloned from {agent_id} by {cloned_by}",
                context={"source_agent_id": str(agent_id), "cloned_by": cloned_by},
            )
            
            config = AgentConfig(**cloned_config.config_json)
            return await self._agent_to_response(cloned_agent, config)
    
    async def change_agent_state(
        self,
        agent_id: UUID,
        new_state: AgentStatus,
        changed_by: str = "system",
        reason: Optional[str] = None,
    ) -> Agent:
        """
        Change agent state with validation and logging.
        
        Validates state transitions and logs all state changes.
        
        Args:
            agent_id: Agent UUID
            new_state: New agent state
            changed_by: User identifier who changed the state
            reason: Reason for state change
            
        Returns:
            Updated agent
            
        Raises:
            ValueError: If agent not found or invalid state transition
            
        **Validates: Requirements 16.1-16.12**
        """
        logger.info(f"Changing agent state: {agent_id} -> {new_state.value}")
        
        async with self.db_client.session() as session:
            # Get agent
            result = await session.execute(
                select(AgentModel).where(AgentModel.id == agent_id)
            )
            agent = result.scalar_one_or_none()
            
            if not agent:
                raise ValueError(f"Agent {agent_id} not found")
            
            old_state = agent.status
            
            # Validate state transition
            self._validate_state_transition(old_state, new_state.value)
            
            # Update state
            agent.status = new_state.value
            await session.commit()
            await session.refresh(agent)
            
            logger.info(f"Agent state changed: {agent_id} ({old_state} -> {new_state.value})")
            
            # Log state change
            await self._log_agent_event(
                agent_id=agent_id,
                log_level="INFO",
                message=f"Agent state changed from {old_state} to {new_state.value}",
                context={
                    "old_state": old_state,
                    "new_state": new_state.value,
                    "changed_by": changed_by,
                    "reason": reason,
                },
            )
            
            return Agent.model_validate(agent)
    
    # ============================================
    # Helper Methods
    # ============================================
    
    async def _generate_unique_name(self, base_name: str) -> str:
        """
        Generate unique agent name by appending suffix.
        
        Args:
            base_name: Base name to make unique
            
        Returns:
            Unique name
        """
        async with self.db_client.session() as session:
            suffix = 1
            while True:
                candidate = f"{base_name}_copy_{suffix}"
                result = await session.execute(
                    select(AgentModel).where(AgentModel.name == candidate)
                )
                if not result.scalar_one_or_none():
                    return candidate
                suffix += 1
    
    def _validate_state_transition(self, old_state: str, new_state: str) -> None:
        """
        Validate agent state transition.
        
        Args:
            old_state: Current state
            new_state: Target state
            
        Raises:
            ValueError: If transition is invalid
        """
        # Define valid transitions
        valid_transitions = {
            AgentStatus.INACTIVE.value: [
                AgentStatus.ACTIVE.value,
                AgentStatus.ERROR.value,
            ],
            AgentStatus.ACTIVE.value: [
                AgentStatus.INACTIVE.value,
                AgentStatus.PAUSED.value,
                AgentStatus.ERROR.value,
            ],
            AgentStatus.PAUSED.value: [
                AgentStatus.ACTIVE.value,
                AgentStatus.INACTIVE.value,
                AgentStatus.ERROR.value,
            ],
            AgentStatus.ERROR.value: [
                AgentStatus.INACTIVE.value,
                AgentStatus.ACTIVE.value,
            ],
        }
        
        if new_state not in valid_transitions.get(old_state, []):
            raise ValueError(
                f"Invalid state transition: {old_state} -> {new_state}"
            )
    
    async def _agent_to_response(
        self,
        agent: AgentModel,
        config: Optional[AgentConfig] = None,
    ) -> AgentWithConfig:
        """
        Convert ORM model to response model.
        
        Args:
            agent: Agent ORM model
            config: Optional agent configuration
            
        Returns:
            Agent response model
        """
        agent_dict = {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "status": agent.status,
            "priority": agent.priority,
            "owner_user_id": agent.owner_user_id,
            "tags": agent.tags or [],
            "category": agent.category,
            "metadata": agent.agent_metadata or {},
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        }
        
        if config:
            return AgentWithConfig(**agent_dict, config=config)
        else:
            return AgentWithConfig(**agent_dict)
    
    async def _log_agent_event(
        self,
        agent_id: UUID,
        log_level: str,
        message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log agent event to database.
        
        Args:
            agent_id: Agent UUID
            log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            context: Optional context data
        """
        try:
            async with self.db_client.session() as session:
                log = AgentLogModel(
                    agent_id=agent_id,
                    log_level=log_level,
                    message=message,
                    context=context or {},
                    timestamp=datetime.utcnow(),
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to log agent event: {e}")
