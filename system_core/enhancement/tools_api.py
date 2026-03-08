"""
External Tools API endpoints.

This module provides FastAPI routes for external tool management:
- POST /api/tools/{tool_name}/execute - Execute external tool
- GET /api/tools - List all tools
- GET /api/tools/{tool_name} - Get tool details
"""

from typing import Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from system_core.enhancement.external_tools import ExternalToolRegistry
from system_core.config import get_logger

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/tools", tags=["external_tools"])

# Initialize tool registry (singleton)
_tool_registry = None

def get_tool_registry() -> ExternalToolRegistry:
    """Get or create tool registry instance."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ExternalToolRegistry()
    return _tool_registry

# Request/Response models
class ToolExecuteRequest(BaseModel):
    """Tool execution request."""
    parameters: dict[str, Any]

class ToolExecuteResponse(BaseModel):
    """Tool execution response."""
    success: bool
    result: Any = None
    error: str = None
    stdout: str = None
    stderr: str = None
    return_code: int = None

class ToolInfo(BaseModel):
    """Tool information."""
    name: str
    source_type: str
    integration_method: str
    risk_warning: str
    enabled: bool

class ToolListResponse(BaseModel):
    """Tool list response."""
    tools: list[ToolInfo]
    total_count: int

# API Endpoints
@router.post("/{tool_name}/execute", response_model=ToolExecuteResponse)
async def execute_tool(
    tool_name: str,
    request: ToolExecuteRequest
) -> ToolExecuteResponse:
    """
    Execute external tool with parameters.
    
    Args:
        tool_name: Name of tool to execute
        request: Tool execution request with parameters
        
    Returns:
        Tool execution result
    """
    try:
        registry = get_tool_registry()
        
        # Get tool
        tool = registry.get_tool(tool_name)
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found"
            )
        
        # Log risk warning
        logger.warning("tool_execution_requested",
                      tool_name=tool_name,
                      risk_warning=tool.risk_warning)
        
        # Execute tool
        result = registry.execute_tool(tool_name, request.parameters)
        
        logger.info("tool_executed",
                   tool_name=tool_name,
                   success=result.get('success', False))
        
        return ToolExecuteResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("tool_execution_api_failed",
                    tool_name=tool_name,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool execution failed: {str(e)}"
        )

@router.get("", response_model=ToolListResponse)
async def list_tools(
    enabled_only: bool = False
) -> ToolListResponse:
    """
    List all registered external tools.
    
    Args:
        enabled_only: Only return enabled tools
        
    Returns:
        List of tools
    """
    try:
        registry = get_tool_registry()
        tools_list = registry.list_tools(enabled_only=enabled_only)
        
        logger.info("tools_listed",
                   total_count=len(tools_list),
                   enabled_only=enabled_only)
        
        return ToolListResponse(
            tools=[ToolInfo(**tool) for tool in tools_list],
            total_count=len(tools_list)
        )
        
    except Exception as e:
        logger.error("tools_list_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tools: {str(e)}"
        )

@router.get("/{tool_name}", response_model=ToolInfo)
async def get_tool(tool_name: str) -> ToolInfo:
    """
    Get tool details by name.
    
    Args:
        tool_name: Name of tool
        
    Returns:
        Tool information
    """
    try:
        registry = get_tool_registry()
        tool = registry.get_tool(tool_name)
        
        if not tool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{tool_name}' not found"
            )
        
        logger.info("tool_details_retrieved", tool_name=tool_name)
        
        return ToolInfo(
            name=tool.name,
            source_type=tool.source_type,
            integration_method=tool.integration_method,
            risk_warning=tool.risk_warning,
            enabled=tool.enabled
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("tool_details_failed",
                    tool_name=tool_name,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tool details: {str(e)}"
        )
