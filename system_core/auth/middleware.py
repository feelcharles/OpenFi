"""
FastAPI authentication middleware and dependencies.

This module provides FastAPI dependencies for JWT validation,
user authentication, and role-based access control.
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.auth.jwt_handler import verify_token
from system_core.auth.rbac import Role, check_permission
from system_core.database.models import User
from system_core.database.client import get_db
from system_core.config import get_logger

logger = get_logger(__name__)

# HTTP Bearer token security scheme
security = HTTPBearer()

class CurrentUser:
    """Current authenticated user information."""
    
    def __init__(
        self,
        user_id: UUID,
        username: str,
        email: str,
        role: str
    ):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.role = role
    
    def has_role(self, required_role: Role) -> bool:
        """Check if user has required role."""
        return check_permission(self.role, required_role)
    
    def __repr__(self):
        return f"<CurrentUser(user_id={self.user_id}, username={self.username}, role={self.role})>"

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> CurrentUser:
    """
    FastAPI dependency to get current authenticated user.
    
    Validates JWT token and extracts user information.
    
    Args:
        credentials: HTTP Bearer token credentials
        db: Database session
    
    Returns:
        CurrentUser object with user information
    
    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    token = credentials.credentials
    
    try:
        # Verify JWT token
        payload = verify_token(token)
        
        # Extract user information
        user_id = UUID(payload["sub"])
        username = payload["username"]
        role = payload["role"]
        
        # Validate user exists in database (SQLAlchemy 2.0)
        email = payload.get("email", "")
        
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            logger.warning(
                "user_not_found_in_database",
                user_id=str(user_id),
                username=username
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        email = user.email
        
        current_user = CurrentUser(
            user_id=user_id,
            username=username,
            email=email,
            role=role
        )
        
        logger.debug(
            "user_authenticated",
            user_id=str(user_id),
            username=username,
            role=role
        )
        
        return current_user
        
    except ValueError as e:
        # Invalid UUID format
        logger.warning("invalid_user_id_format", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        # Token validation failed
        logger.warning("token_validation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_role(required_role: Role):
    """
    FastAPI dependency factory for role-based access control.
    
    Creates a dependency that checks if the current user has the required role.
    
    Args:
        required_role: Minimum required role
    
    Returns:
        FastAPI dependency function
    
    Example:
        @app.get("/admin/users", dependencies=[Depends(require_role(Role.ADMIN))])
        async def list_users():
            ...
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        """Check if user has required role."""
        if not current_user.has_role(required_role):
            logger.warning(
                "insufficient_permissions",
                user_id=str(current_user.user_id),
                username=current_user.username,
                user_role=current_user.role,
                required_role=required_role.value
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role.value}",
            )
        
        return current_user
    
    return role_checker

def require_admin(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    FastAPI dependency to require admin role.
    
    Convenience function for requiring admin access.
    """
    if not current_user.has_role(Role.ADMIN):
        logger.warning(
            "admin_access_denied",
            user_id=str(current_user.user_id),
            username=current_user.username,
            role=current_user.role
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    
    return current_user

def require_trader(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    FastAPI dependency to require trader role or higher.
    
    Allows admin and trader roles.
    """
    if not current_user.has_role(Role.TRADER):
        logger.warning(
            "trader_access_denied",
            user_id=str(current_user.user_id),
            username=current_user.username,
            role=current_user.role
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trader access required",
        )
    
    return current_user

