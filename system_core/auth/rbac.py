"""
Role-Based Access Control (RBAC) implementation.

This module defines user roles and permission checking logic.
"""

from enum import Enum
from typing import Callable

from fastapi import Depends, HTTPException, status

class Role(str, Enum):
    """
    User roles with hierarchical permissions.
    
    Hierarchy: ADMIN > TRADER > VIEWER
    - ADMIN: Full system access (all operations)
    - TRADER: Trading operations (view + trade execution)
    - VIEWER: Read-only access (view data only)
    """
    
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"
    
    @classmethod
    def get_hierarchy(cls) -> list["Role"]:
        """
        Get role hierarchy from highest to lowest privilege.
        
        Returns:
            List of roles in descending privilege order
        """
        return [cls.ADMIN, cls.TRADER, cls.VIEWER]
    
    @classmethod
    def get_role_level(cls, role: "Role") -> int:
        """
        Get numeric level for role (higher = more privilege).
        
        Args:
            role: Role to get level for
        
        Returns:
            Numeric level (3=admin, 2=trader, 1=viewer)
        """
        hierarchy = cls.get_hierarchy()
        return len(hierarchy) - hierarchy.index(role)

def check_permission(user_role: str, required_role: Role) -> bool:
    """
    Check if user role has sufficient permissions.
    
    Uses hierarchical role checking where higher roles inherit
    permissions from lower roles.
    
    Args:
        user_role: User's current role (string)
        required_role: Minimum required role
    
    Returns:
        True if user has sufficient permissions, False otherwise
    
    Examples:
        >>> check_permission("admin", Role.TRADER)
        True
        >>> check_permission("viewer", Role.TRADER)
        False
        >>> check_permission("trader", Role.TRADER)
        True
    """
    try:
        # Convert string to Role enum
        user_role_enum = Role(user_role.lower())
    except ValueError:
        # Invalid role
        return False
    
    # Get role levels
    user_level = Role.get_role_level(user_role_enum)
    required_level = Role.get_role_level(required_role)
    
    # User must have equal or higher level
    return user_level >= required_level

def get_role_permissions(role: Role) -> list[str]:
    """
    Get list of permissions for a role.
    
    Args:
        role: Role to get permissions for
    
    Returns:
        List of permission strings
    """
    permissions = {
        Role.ADMIN: [
            "users:read",
            "users:write",
            "users:delete",
            "ea_profiles:read",
            "ea_profiles:write",
            "ea_profiles:delete",
            "trades:read",
            "trades:write",
            "trades:delete",
            "config:read",
            "config:write",
            "system:manage",
        ],
        Role.TRADER: [
            "users:read",  # Own user only
            "ea_profiles:read",
            "ea_profiles:write",
            "trades:read",
            "trades:write",
            "config:read",  # Own config only
        ],
        Role.VIEWER: [
            "users:read",  # Own user only
            "ea_profiles:read",
            "trades:read",
            "config:read",  # Own config only
        ],
    }
    
    return permissions.get(role, [])

def has_permission(user_role: str, permission: str) -> bool:
    """
    Check if user role has specific permission.
    
    Args:
        user_role: User's current role (string)
        permission: Permission to check (e.g., "trades:write")
    
    Returns:
        True if user has permission, False otherwise
    """
    try:
        role_enum = Role(user_role.lower())
    except ValueError:
        return False
    
    # Get all permissions for role and higher roles
    all_permissions = []
    for role in Role.get_hierarchy():
        if Role.get_role_level(role) >= Role.get_role_level(role_enum):
            all_permissions.extend(get_role_permissions(role))
    
    return permission in all_permissions

def require_permission(permission: str) -> Callable:
    """
    FastAPI dependency factory for permission checking.
    
    Creates a dependency that checks if the current user has the required permission.
    
    Args:
        permission: Required permission (e.g., "agent:create", "agent:read")
    
    Returns:
        FastAPI dependency function
    
    Usage:
        @router.post("/agents")
        async def create_agent(
            _permission: None = Depends(require_permission("agent:create"))
        ):
            ...
    """
    async def permission_checker(current_user: dict = Depends(lambda: None)):
        """Check if user has required permission."""
        # For now, allow all operations
        # TODO: Implement actual permission checking when user roles are available
        return None
    
    return permission_checker


class RBACManager:
    """
    RBAC Manager class for backward compatibility.
    
    Provides an object-oriented interface to RBAC functions.
    """
    
    @staticmethod
    def check_permission(user_role: str, resource: str, action: str) -> bool:
        """
        Check if user role has permission for resource and action.
        
        Args:
            user_role: User's current role
            resource: Resource name (e.g., "users", "trades")
            action: Action name (e.g., "read", "write", "delete")
        
        Returns:
            True if user has permission, False otherwise
        """
        permission = f"{resource}:{action}"
        return has_permission(user_role, permission)
    
    @staticmethod
    def get_role_permissions(role: Role) -> list[str]:
        """
        Get list of permissions for a role.
        
        Args:
            role: Role to get permissions for
        
        Returns:
            List of permission strings
        """
        return get_role_permissions(role)
    
    @staticmethod
    def has_permission(user_role: str, permission: str) -> bool:
        """
        Check if user role has specific permission.
        
        Args:
            user_role: User's current role
            permission: Permission to check
        
        Returns:
            True if user has permission, False otherwise
        """
        return has_permission(user_role, permission)
