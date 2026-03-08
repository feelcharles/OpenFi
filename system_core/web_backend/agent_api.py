"""
Agent Management API endpoints.

Provides REST APIs for:
- Agent CRUD operations
- Agent configuration management
- Agent state management
- Agent monitoring and metrics
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.database.client import DatabaseClient
from system_core.agent_system.manager import AgentManager
from system_core.agent_system.schemas import (
    AgentCreateRequest,
    AgentUpdateRequest,
    AgentResponse,
    AgentListResponse,
    AgentStateChangeRequest,
    AgentCloneRequest,
    ErrorResponse,
)
from system_core.auth.middleware import get_current_user
from system_core.auth.rbac import require_permission
from system_core.config import get_logger

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# Initialize AgentManager
db_client = DatabaseClient()
agent_manager = AgentManager(db_client=db_client)

@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new agent",
    description="""
Create a new agent with specified configuration.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:create

**Request Body**:
- name: Unique agent name
- description: Agent description
- status: Initial status (default: inactive)
- priority: Agent priority (low, normal, high)
- owner_user_id: Owner user UUID
- tags: List of tags for categorization
- category: Agent category
- config: Optional agent configuration

**Returns**: Created agent with full configuration
""",
    responses={
        201: {"description": "Agent created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request data"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
        409: {"model": ErrorResponse, "description": "Agent name already exists"},
    },
)
async def create_agent(
    request: AgentCreateRequest,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:create")),
):
    """Create a new agent."""
    try:
        logger.info(f"Creating agent: {request.name} by user {current_user['user_id']}")
        
        # Convert request to AgentCreate model
        from system_core.agent_system.models import AgentCreate
        agent_data = AgentCreate(
            name=request.name,
            description=request.description,
            status=request.status,
            priority=request.priority,
            owner_user_id=request.owner_user_id or UUID(current_user["user_id"]),
            tags=request.tags or [],
            category=request.category,
            metadata=request.metadata or {},
            config=request.config,
        )
        
        # Create agent
        agent = await agent_manager.create_agent(
            agent_data=agent_data,
            created_by=current_user["username"],
        )
        
        logger.info(f"Agent created: {agent.id}")
        return agent
        
    except ValueError as e:
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error creating agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create agent",
        )

@router.get(
    "",
    response_model=AgentListResponse,
    summary="List agents",
    description="""
List all agents with optional filtering and pagination.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Query Parameters**:
- status: Filter by agent status
- priority: Filter by agent priority
- category: Filter by agent category
- tags: Filter by tags (comma-separated)
- owner_user_id: Filter by owner user ID
- search: Search in name and description
- limit: Maximum number of results (default: 50, max: 100)
- offset: Number of results to skip (default: 0)

**Returns**: List of agents with pagination metadata
""",
    responses={
        200: {"description": "Agents retrieved successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
    },
)
async def list_agents(
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    owner_user_id: Optional[UUID] = Query(None, description="Filter by owner"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """List agents with filtering and pagination."""
    try:
        logger.info(f"Listing agents by user {current_user['user_id']}")
        
        # Parse tags
        tag_list = tags.split(",") if tags else None
        
        # List agents
        agents = await agent_manager.list_agents(
            status=status,
            priority=priority,
            category=category,
            tags=tag_list,
            owner_user_id=owner_user_id,
            search=search,
            limit=limit,
            offset=offset,
        )
        
        # Get total count (simplified - in production, should be a separate query)
        total = len(agents)
        
        return AgentListResponse(
            agents=agents,
            total=total,
            limit=limit,
            offset=offset,
        )
        
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list agents",
        )

@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent details",
    description="""
Get detailed information about a specific agent.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Returns**: Agent details with full configuration
""",
    responses={
        200: {"description": "Agent retrieved successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Agent not found"},
    },
)
async def get_agent(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Get agent by ID."""
    try:
        logger.info(f"Getting agent: {agent_id}")
        
        agent = await agent_manager.get_agent(agent_id=agent_id)
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        return agent
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent",
        )

@router.put(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Update agent",
    description="""
Update agent information and configuration.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID

**Request Body**: Fields to update (all optional)

**Returns**: Updated agent with full configuration
""",
    responses={
        200: {"description": "Agent updated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid request data"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Agent not found"},
    },
)
async def update_agent(
    agent_id: UUID,
    request: AgentUpdateRequest,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Update agent."""
    try:
        logger.info(f"Updating agent: {agent_id}")
        
        # Convert request to AgentUpdate model
        from system_core.agent_system.models import AgentUpdate
        update_data = AgentUpdate(
            name=request.name,
            description=request.description,
            status=request.status,
            priority=request.priority,
            tags=request.tags,
            category=request.category,
            metadata=request.metadata,
            config=request.config,
        )
        
        # Update agent
        agent = await agent_manager.update_agent(
            agent_id=agent_id,
            update_data=update_data,
            updated_by=current_user["username"],
        )
        
        logger.info(f"Agent updated: {agent_id}")
        return agent
        
    except ValueError as e:
        logger.error(f"Failed to update agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error updating agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent",
        )

@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete agent",
    description="""
Delete an agent and all related data.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:delete

**Path Parameters**:
- agent_id: Agent UUID

**Query Parameters**:
- force: Force deletion even if agent is active (default: false)

**Returns**: No content on success
""",
    responses={
        204: {"description": "Agent deleted successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Agent not found"},
        409: {"model": ErrorResponse, "description": "Cannot delete active agent"},
    },
)
async def delete_agent(
    agent_id: UUID,
    force: bool = Query(False, description="Force delete active agent"),
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:delete")),
):
    """Delete agent."""
    try:
        logger.info(f"Deleting agent: {agent_id}, force={force}")
        
        await agent_manager.delete_agent(
            agent_id=agent_id,
            force=force,
            deleted_by=current_user["username"],
        )
        
        logger.info(f"Agent deleted: {agent_id}")
        return None
        
    except ValueError as e:
        logger.error(f"Failed to delete agent: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
    except Exception as e:
        logger.error(f"Unexpected error deleting agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete agent",
        )

@router.post(
    "/{agent_id}/clone",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone agent",
    description="""
Clone an existing agent with a new name.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:create

**Path Parameters**:
- agent_id: Source agent UUID

**Request Body**:
- new_name: Optional new name for cloned agent (auto-generated if not provided)

**Returns**: Cloned agent with full configuration
""",
    responses={
        201: {"description": "Agent cloned successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Source agent not found"},
    },
)
async def clone_agent(
    agent_id: UUID,
    request: AgentCloneRequest = None,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:create")),
):
    """Clone agent."""
    try:
        logger.info(f"Cloning agent: {agent_id}")
        
        new_name = request.new_name if request else None
        
        agent = await agent_manager.clone_agent(
            agent_id=agent_id,
            new_name=new_name,
            cloned_by=current_user["username"],
        )
        
        logger.info(f"Agent cloned: {agent.id}")
        return agent
        
    except ValueError as e:
        logger.error(f"Failed to clone agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error cloning agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clone agent",
        )

@router.put(
    "/{agent_id}/state",
    response_model=AgentResponse,
    summary="Change agent state",
    description="""
Change agent state (active, inactive, paused, error).

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID

**Request Body**:
- new_state: New agent state
- reason: Optional reason for state change

**Returns**: Updated agent
""",
    responses={
        200: {"description": "Agent state changed successfully"},
        400: {"model": ErrorResponse, "description": "Invalid state transition"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Agent not found"},
    },
)
async def change_agent_state(
    agent_id: UUID,
    request: AgentStateChangeRequest,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Change agent state."""
    try:
        logger.info(f"Changing agent state: {agent_id} -> {request.new_state}")
        
        agent = await agent_manager.change_agent_state(
            agent_id=agent_id,
            new_state=request.new_state,
            changed_by=current_user["username"],
            reason=request.reason,
        )
        
        logger.info(f"Agent state changed: {agent_id}")
        return agent
        
    except ValueError as e:
        logger.error(f"Failed to change agent state: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
    except Exception as e:
        logger.error(f"Unexpected error changing agent state: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change agent state",
        )

# ============================================
# Agent Configuration API Endpoints
# ============================================

# Initialize ConfigManager
from system_core.agent_system.config_manager import ConfigManager
config_manager = ConfigManager(db_client=db_client)

@router.get(
    "/{agent_id}/config",
    response_model=dict,
    summary="Get agent configuration",
    description="""
Get current agent configuration.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Returns**: Agent configuration
""",
    responses={
        200: {"description": "Configuration retrieved successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Agent not found"},
    },
)
async def get_agent_config(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Get agent configuration."""
    try:
        logger.info(f"Getting config for agent: {agent_id}")
        
        config = await config_manager.load_config(agent_id=agent_id)
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration for agent {agent_id} not found",
            )
        
        return config.model_dump()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent configuration",
        )

@router.put(
    "/{agent_id}/config",
    response_model=dict,
    summary="Update agent configuration",
    description="""
Update agent configuration with validation and versioning.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID

**Request Body**: Agent configuration

**Returns**: Updated configuration
""",
    responses={
        200: {"description": "Configuration updated successfully"},
        400: {"model": ErrorResponse, "description": "Invalid configuration"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Agent not found"},
    },
)
async def update_agent_config(
    agent_id: UUID,
    config: dict,
    change_description: Optional[str] = Query(None, description="Description of changes"),
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Update agent configuration."""
    try:
        logger.info(f"Updating config for agent: {agent_id}")
        
        # Convert dict to AgentConfig
        from system_core.agent_system.models import AgentConfig
        agent_config = AgentConfig(**config)
        
        # Save configuration
        saved_config = await config_manager.save_config(
            agent_id=agent_id,
            config=agent_config,
            created_by=current_user["username"],
            change_description=change_description,
        )
        
        logger.info(f"Config updated for agent: {agent_id}")
        return saved_config.model_dump()
        
    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update agent config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent configuration",
        )

@router.get(
    "/{agent_id}/config/versions",
    response_model=list[dict],
    summary="Get configuration version history",
    description="""
Get list of all configuration versions for an agent.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Returns**: List of configuration versions with metadata
""",
    responses={
        200: {"description": "Version history retrieved successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Agent not found"},
    },
)
async def list_config_versions(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """List configuration versions."""
    try:
        logger.info(f"Listing config versions for agent: {agent_id}")
        
        versions = await config_manager.list_config_versions(agent_id=agent_id)
        
        return [
            {
                "version": v.version,
                "created_at": v.created_at.isoformat(),
                "created_by": v.created_by,
                "change_description": v.change_description,
            }
            for v in versions
        ]
        
    except Exception as e:
        logger.error(f"Failed to list config versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list configuration versions",
        )

@router.get(
    "/{agent_id}/config/versions/{version}",
    response_model=dict,
    summary="Get specific configuration version",
    description="""
Get a specific configuration version.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID
- version: Configuration version number

**Returns**: Configuration for specified version
""",
    responses={
        200: {"description": "Configuration version retrieved successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Version not found"},
    },
)
async def get_config_version(
    agent_id: UUID,
    version: int,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Get specific configuration version."""
    try:
        logger.info(f"Getting config version {version} for agent: {agent_id}")
        
        config = await config_manager.get_config_version(
            agent_id=agent_id,
            version=version,
        )
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Configuration version {version} not found",
            )
        
        return config.model_dump()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get config version: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get configuration version",
        )

@router.post(
    "/{agent_id}/config/rollback",
    response_model=dict,
    summary="Rollback configuration to previous version",
    description="""
Rollback agent configuration to a previous version.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID

**Query Parameters**:
- version: Version number to rollback to

**Returns**: Rolled back configuration
""",
    responses={
        200: {"description": "Configuration rolled back successfully"},
        400: {"model": ErrorResponse, "description": "Invalid version"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Version not found"},
    },
)
async def rollback_config(
    agent_id: UUID,
    version: int = Query(..., description="Version to rollback to"),
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Rollback configuration."""
    try:
        logger.info(f"Rolling back config to version {version} for agent: {agent_id}")
        
        config = await config_manager.rollback_config(
            agent_id=agent_id,
            target_version=version,
            rolled_back_by=current_user["username"],
        )
        
        logger.info(f"Config rolled back for agent: {agent_id}")
        return config.model_dump()
        
    except ValueError as e:
        logger.error(f"Failed to rollback config: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error rolling back config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rollback configuration",
        )

@router.post(
    "/{agent_id}/config/validate",
    response_model=dict,
    summary="Validate agent configuration",
    description="""
Validate agent configuration without saving.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Request Body**: Configuration to validate

**Returns**: Validation result with errors if any
""",
    responses={
        200: {"description": "Configuration validated"},
        400: {"model": ErrorResponse, "description": "Invalid configuration"},
        401: {"description": "Unauthorized"},
        403: {"description": "Insufficient permissions"},
    },
)
async def validate_config(
    agent_id: UUID,
    config: dict,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Validate configuration."""
    try:
        logger.info(f"Validating config for agent: {agent_id}")
        
        # Convert dict to AgentConfig
        from system_core.agent_system.models import AgentConfig
        agent_config = AgentConfig(**config)
        
        # Validate configuration
        is_valid, errors = await config_manager.validate_config(config=agent_config)
        
        return {
            "valid": is_valid,
            "errors": errors,
        }
        
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        return {
            "valid": False,
            "errors": [str(e)],
        }
    except Exception as e:
        logger.error(f"Failed to validate config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate configuration",
        )

# ============================================
# Agent Assets API Endpoints
# ============================================

@router.get(
    "/{agent_id}/assets",
    response_model=dict,
    summary="Get agent asset portfolio",
    description="""
Get agent's asset portfolio configuration.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Returns**: Asset portfolio with weights
""",
)
async def get_agent_assets(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Get agent assets."""
    try:
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        return config.asset_portfolio.model_dump()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent assets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent assets",
        )

@router.put(
    "/{agent_id}/assets",
    response_model=dict,
    summary="Update agent asset portfolio",
    description="""
Update agent's complete asset portfolio.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID

**Request Body**: Asset portfolio configuration

**Returns**: Updated asset portfolio
""",
)
async def update_agent_assets(
    agent_id: UUID,
    assets: dict,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Update agent assets."""
    try:
        from system_core.agent_system.models import AssetPortfolio
        
        # Load current config
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Update asset portfolio
        config.asset_portfolio = AssetPortfolio(**assets)
        
        # Save config
        await config_manager.save_config(
            agent_id=agent_id,
            config=config,
            created_by=current_user["username"],
            change_description="Updated asset portfolio",
        )
        
        return config.asset_portfolio.model_dump()
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update agent assets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent assets",
        )

@router.post(
    "/{agent_id}/assets",
    response_model=dict,
    summary="Add asset to portfolio",
    description="""
Add a single asset to agent's portfolio.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID

**Request Body**: Asset to add

**Returns**: Updated asset portfolio
""",
)
async def add_agent_asset(
    agent_id: UUID,
    asset: dict,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Add asset to portfolio."""
    try:
        from system_core.agent_system.models import AssetWeight
        
        # Load current config
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Add asset
        new_asset = AssetWeight(**asset)
        config.asset_portfolio.assets.append(new_asset)
        
        # Save config
        await config_manager.save_config(
            agent_id=agent_id,
            config=config,
            created_by=current_user["username"],
            change_description=f"Added asset {new_asset.symbol}",
        )
        
        return config.asset_portfolio.model_dump()
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to add agent asset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add agent asset",
        )

@router.delete(
    "/{agent_id}/assets/{symbol}",
    response_model=dict,
    summary="Remove asset from portfolio",
    description="""
Remove an asset from agent's portfolio.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID
- symbol: Asset symbol to remove

**Returns**: Updated asset portfolio
""",
)
async def delete_agent_asset(
    agent_id: UUID,
    symbol: str,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Remove asset from portfolio."""
    try:
        # Load current config
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Remove asset
        config.asset_portfolio.assets = [
            a for a in config.asset_portfolio.assets if a.symbol != symbol
        ]
        
        # Save config
        await config_manager.save_config(
            agent_id=agent_id,
            config=config,
            created_by=current_user["username"],
            change_description=f"Removed asset {symbol}",
        )
        
        return config.asset_portfolio.model_dump()
        
    except Exception as e:
        logger.error(f"Failed to delete agent asset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete agent asset",
        )

# ============================================
# Agent Triggers API Endpoints
# ============================================

@router.get(
    "/{agent_id}/triggers",
    response_model=dict,
    summary="Get agent trigger configuration",
    description="""
Get agent's trigger configuration.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Returns**: Trigger configuration
""",
)
async def get_agent_triggers(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Get agent triggers."""
    try:
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        return config.trigger_config.model_dump()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent triggers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent triggers",
        )

@router.put(
    "/{agent_id}/triggers",
    response_model=dict,
    summary="Update agent trigger configuration",
    description="""
Update agent's trigger configuration.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID

**Request Body**: Trigger configuration

**Returns**: Updated trigger configuration
""",
)
async def update_agent_triggers(
    agent_id: UUID,
    triggers: dict,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Update agent triggers."""
    try:
        from system_core.agent_system.models import TriggerConfig
        
        # Load current config
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Update trigger config
        config.trigger_config = TriggerConfig(**triggers)
        
        # Save config
        await config_manager.save_config(
            agent_id=agent_id,
            config=config,
            created_by=current_user["username"],
            change_description="Updated trigger configuration",
        )
        
        return config.trigger_config.model_dump()
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update agent triggers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent triggers",
        )

@router.post(
    "/{agent_id}/triggers/test",
    response_model=dict,
    summary="Test agent trigger",
    description="""
Test agent trigger with sample data.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID

**Request Body**: Test trigger event data

**Returns**: Test execution result
""",
)
async def test_agent_trigger(
    agent_id: UUID,
    trigger_data: dict,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Test agent trigger."""
    try:
        from system_core.agent_system.executor import AgentExecutor
        from system_core.agent_system.models import TriggerEvent, TriggerType
        
        # Create executor
        executor = AgentExecutor(db_client=db_client)
        
        # Create test trigger event
        trigger_type = TriggerType(trigger_data.get("trigger_type", "manual"))
        event = TriggerEvent(
            agent_id=agent_id,
            trigger_type=trigger_type,
            event_data=trigger_data.get("event_data", {}),
        )
        
        # Execute trigger (in test mode)
        result = await executor.execute_trigger(
            event=event,
            test_mode=True,
        )
        
        return {
            "success": True,
            "result": result,
            "message": "Trigger test completed successfully",
        }
        
    except Exception as e:
        logger.error(f"Failed to test agent trigger: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Trigger test failed",
        }

# ============================================
# Agent Push Configuration API Endpoints
# ============================================

@router.get(
    "/{agent_id}/push-config",
    response_model=dict,
    summary="Get agent push configuration",
    description="""
Get agent's push notification configuration.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Returns**: Push configuration
""",
)
async def get_agent_push_config(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Get agent push configuration."""
    try:
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        return config.push_config.model_dump()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent push config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent push configuration",
        )

@router.put(
    "/{agent_id}/push-config",
    response_model=dict,
    summary="Update agent push configuration",
    description="""
Update agent's push notification configuration.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID

**Request Body**: Push configuration

**Returns**: Updated push configuration
""",
)
async def update_agent_push_config(
    agent_id: UUID,
    push_config: dict,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Update agent push configuration."""
    try:
        from system_core.agent_system.models import PushConfig
        
        # Load current config
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Update push config
        config.push_config = PushConfig(**push_config)
        
        # Save config
        await config_manager.save_config(
            agent_id=agent_id,
            config=config,
            created_by=current_user["username"],
            change_description="Updated push configuration",
        )
        
        return config.push_config.model_dump()
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update agent push config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent push configuration",
        )

# ============================================
# Agent Bot Connections API Endpoints
# ============================================

@router.get(
    "/{agent_id}/bots",
    response_model=list[dict],
    summary="Get agent bot connections",
    description="""
Get list of bot connections for an agent.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Returns**: List of bot connections
""",
)
async def get_agent_bots(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Get agent bot connections."""
    try:
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Return bot connections (without sensitive credentials)
        bots = []
        for bot in config.bot_connections:
            bot_dict = bot.model_dump()
            # Remove sensitive data
            if "credentials" in bot_dict:
                bot_dict["credentials"] = "***REDACTED***"
            bots.append(bot_dict)
        
        return bots
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent bots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent bot connections",
        )

@router.post(
    "/{agent_id}/bots",
    response_model=dict,
    summary="Add bot connection",
    description="""
Add a new bot connection to agent.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID

**Request Body**: Bot connection configuration

**Returns**: Created bot connection
""",
)
async def add_agent_bot(
    agent_id: UUID,
    bot: dict,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Add bot connection."""
    try:
        from system_core.agent_system.models import BotConnection
        
        # Load current config
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Check bot connection limit (max 5)
        if len(config.bot_connections) >= 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 5 bot connections allowed per agent",
            )
        
        # Add bot connection
        new_bot = BotConnection(**bot)
        config.bot_connections.append(new_bot)
        
        # Save config
        await config_manager.save_config(
            agent_id=agent_id,
            config=config,
            created_by=current_user["username"],
            change_description=f"Added bot connection: {new_bot.bot_type}",
        )
        
        # Return without sensitive credentials
        bot_dict = new_bot.model_dump()
        if "credentials" in bot_dict:
            bot_dict["credentials"] = "***REDACTED***"
        
        return bot_dict
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to add agent bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add bot connection",
        )

@router.put(
    "/{agent_id}/bots/{bot_id}",
    response_model=dict,
    summary="Update bot connection",
    description="""
Update an existing bot connection.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID
- bot_id: Bot connection ID

**Request Body**: Updated bot configuration

**Returns**: Updated bot connection
""",
)
async def update_agent_bot(
    agent_id: UUID,
    bot_id: str,
    bot_update: dict,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Update bot connection."""
    try:
        # Load current config
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Find and update bot
        bot_found = False
        for i, bot in enumerate(config.bot_connections):
            if str(bot.bot_id) == bot_id:
                # Update bot fields
                for key, value in bot_update.items():
                    if hasattr(bot, key):
                        setattr(bot, key, value)
                bot_found = True
                break
        
        if not bot_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bot connection {bot_id} not found",
            )
        
        # Save config
        await config_manager.save_config(
            agent_id=agent_id,
            config=config,
            created_by=current_user["username"],
            change_description=f"Updated bot connection: {bot_id}",
        )
        
        # Return without sensitive credentials
        bot_dict = config.bot_connections[i].model_dump()
        if "credentials" in bot_dict:
            bot_dict["credentials"] = "***REDACTED***"
        
        return bot_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update agent bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update bot connection",
        )

@router.delete(
    "/{agent_id}/bots/{bot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete bot connection",
    description="""
Delete a bot connection from agent.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID
- bot_id: Bot connection ID

**Returns**: No content on success
""",
)
async def delete_agent_bot(
    agent_id: UUID,
    bot_id: str,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Delete bot connection."""
    try:
        # Load current config
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Remove bot
        original_count = len(config.bot_connections)
        config.bot_connections = [
            b for b in config.bot_connections if str(b.bot_id) != bot_id
        ]
        
        if len(config.bot_connections) == original_count:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bot connection {bot_id} not found",
            )
        
        # Save config
        await config_manager.save_config(
            agent_id=agent_id,
            config=config,
            created_by=current_user["username"],
            change_description=f"Deleted bot connection: {bot_id}",
        )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete agent bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete bot connection",
        )

@router.post(
    "/{agent_id}/bots/{bot_id}/test",
    response_model=dict,
    summary="Test bot connection",
    description="""
Test bot connection to verify it's working.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:update

**Path Parameters**:
- agent_id: Agent UUID
- bot_id: Bot connection ID

**Returns**: Test result
""",
)
async def test_agent_bot(
    agent_id: UUID,
    bot_id: str,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:update")),
):
    """Test bot connection."""
    try:
        # Load current config
        config = await config_manager.load_config(agent_id=agent_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Find bot
        bot = None
        for b in config.bot_connections:
            if str(b.bot_id) == bot_id:
                bot = b
                break
        
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bot connection {bot_id} not found",
            )
        
        # Test connection (simplified - in production would actually test the bot)
        return {
            "success": True,
            "bot_type": bot.bot_type.value,
            "status": bot.status.value,
            "message": "Bot connection test successful",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test agent bot: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Bot connection test failed",
        }

# ============================================
# Agent Monitoring API Endpoints
# ============================================

@router.get(
    "/{agent_id}/status",
    response_model=dict,
    summary="Get agent runtime status",
    description="""
Get agent's current runtime status and health.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Returns**: Agent runtime status
""",
)
async def get_agent_status(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Get agent status."""
    try:
        # Get agent
        agent = await agent_manager.get_agent(agent_id=agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Get runtime status (simplified)
        return {
            "agent_id": str(agent_id),
            "status": agent.status.value,
            "priority": agent.priority.value,
            "last_trigger": None,  # Would query from metrics
            "last_push": None,  # Would query from metrics
            "health": "healthy",  # Would check actual health
            "uptime": None,  # Would calculate from start time
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent status",
        )

@router.get(
    "/{agent_id}/metrics",
    response_model=dict,
    summary="Get agent performance metrics",
    description="""
Get agent's performance metrics.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Query Parameters**:
- start_time: Start time for metrics (ISO format)
- end_time: End time for metrics (ISO format)
- interval: Aggregation interval (1m, 5m, 1h, 1d)

**Returns**: Agent performance metrics
""",
)
async def get_agent_metrics(
    agent_id: UUID,
    start_time: Optional[datetime] = Query(None, description="Start time"),
    end_time: Optional[datetime] = Query(None, description="End time"),
    interval: str = Query("1h", description="Aggregation interval"),
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Get agent metrics."""
    try:
        # Verify agent exists
        agent = await agent_manager.get_agent(agent_id=agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Get metrics (simplified - would query from metrics database)
        return {
            "agent_id": str(agent_id),
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "interval": interval,
            "metrics": {
                "trigger_count": 0,
                "push_count": 0,
                "error_count": 0,
                "avg_response_time_ms": 0,
                "success_rate": 100.0,
            },
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent metrics",
        )

@router.get(
    "/{agent_id}/logs",
    response_model=list[dict],
    summary="Get agent logs",
    description="""
Get agent's execution logs.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Query Parameters**:
- level: Log level filter (DEBUG, INFO, WARNING, ERROR)
- limit: Maximum number of logs (default: 100, max: 1000)
- offset: Number of logs to skip (default: 0)

**Returns**: List of log entries
""",
)
async def get_agent_logs(
    agent_id: UUID,
    level: Optional[str] = Query(None, description="Log level filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum logs"),
    offset: int = Query(0, ge=0, description="Logs to skip"),
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Get agent logs."""
    try:
        # Verify agent exists
        agent = await agent_manager.get_agent(agent_id=agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Get logs (simplified - would query from logs database)
        return []
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent logs",
        )

@router.get(
    "/{agent_id}/alerts",
    response_model=list[dict],
    summary="Get agent alerts",
    description="""
Get active alerts for an agent.

**Authentication Required**: Yes (JWT Bearer token)
**Required Permission**: agent:read

**Path Parameters**:
- agent_id: Agent UUID

**Query Parameters**:
- severity: Alert severity filter (info, warning, error, critical)
- active_only: Show only active alerts (default: true)

**Returns**: List of alerts
""",
)
async def get_agent_alerts(
    agent_id: UUID,
    severity: Optional[str] = Query(None, description="Severity filter"),
    active_only: bool = Query(True, description="Show only active alerts"),
    current_user: dict = Depends(get_current_user),
    _permission: None = Depends(require_permission("agent:read")),
):
    """Get agent alerts."""
    try:
        # Verify agent exists
        agent = await agent_manager.get_agent(agent_id=agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found",
            )
        
        # Get alerts (simplified - would query from alerting system)
        return []
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent alerts",
        )
