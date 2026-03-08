"""
Authentication API endpoints.

This module provides FastAPI routes for authentication operations:
- POST /api/auth/login - User login with username/password
- POST /api/auth/refresh - Token refresh
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.auth.jwt_handler import create_access_token, verify_token, get_jwt_handler
from system_core.auth.password import verify_password
from system_core.auth.rate_limiter import check_rate_limit, get_rate_limiter
from system_core.database import get_db
from system_core.database.models import User
from system_core.config import get_logger

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

# Request/Response models
class LoginRequest(BaseModel):
    """Login request payload."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)

class TokenResponse(BaseModel):
    """Token response payload."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_id: str
    username: str
    role: str
    must_change_password: bool = False

class RefreshRequest(BaseModel):
    """Token refresh request payload."""
    token: str

class ChangePasswordRequest(BaseModel):
    """Password change request payload."""
    old_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)

@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    User login endpoint.
    
    Authenticates user with username and password, returns JWT token.
    
    Rate limiting: 5 attempts per 15 minutes per IP.
    IP blocking: 30 minutes after 5 failed attempts.
    
    Args:
        request: FastAPI request object
        login_data: Login credentials
        db: Database session
    
    Returns:
        TokenResponse with JWT token and user information
    
    Raises:
        HTTPException: 401 if credentials are invalid
        HTTPException: 429 if rate limit exceeded
    """
    # Check rate limit
    await check_rate_limit(request)
    
    rate_limiter = get_rate_limiter()
    
    try:
        # Query user from database (SQLAlchemy 2.0 syntax)
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.username == login_data.username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # User not found
            await rate_limiter.record_attempt(request, success=False)
            logger.warning(
                "login_failed_user_not_found",
                username=login_data.username,
                ip=rate_limiter._get_client_ip(request)
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        
        # Verify password
        if not verify_password(login_data.password, user.password_hash):
            # Invalid password
            await rate_limiter.record_attempt(request, success=False)
            logger.warning(
                "login_failed_invalid_password",
                username=login_data.username,
                user_id=str(user.id),
                ip=rate_limiter._get_client_ip(request)
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        
        # Create JWT token
        jwt_handler = get_jwt_handler()
        token = create_access_token(
            user_id=str(user.id),
            username=user.username,
            role=user.role,
            additional_claims={"email": user.email}
        )
        
        # Record successful login
        await rate_limiter.record_attempt(request, success=True)
        
        logger.info(
            "login_successful",
            user_id=str(user.id),
            username=user.username,
            role=user.role,
            ip=rate_limiter._get_client_ip(request)
        )
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=jwt_handler.token_expiration_hours * 3600,
            user_id=str(user.id),
            username=user.username,
            role=user.role,
            must_change_password=user.must_change_password
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Unexpected error
        logger.error(
            "login_error",
            username=login_data.username,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Token refresh endpoint.
    
    Accepts a valid JWT token and returns a new token with extended expiration.
    
    Args:
        refresh_data: Current JWT token
        db: Database session
    
    Returns:
        TokenResponse with new JWT token
    
    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    try:
        # Verify current token
        payload = verify_token(refresh_data.token)
        
        # Extract user information
        user_id = UUID(payload["sub"])
        username = payload["username"]
        role = payload["role"]
        
        # Optional: Validate user still exists and is active (SQLAlchemy 2.0)
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            logger.warning(
                "refresh_failed_user_not_found",
                user_id=str(user_id),
                username=username
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        # Create new token
        jwt_handler = get_jwt_handler()
        new_token = create_access_token(
            user_id=str(user.id),
            username=user.username,
            role=user.role,
            additional_claims={"email": user.email}
        )
        
        logger.info(
            "token_refreshed",
            user_id=str(user.id),
            username=username
        )
        
        return TokenResponse(
            access_token=new_token,
            token_type="bearer",
            expires_in=jwt_handler.token_expiration_hours * 3600,
            user_id=str(user.id),
            username=user.username,
            role=user.role
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Token validation or other error
        logger.error("token_refresh_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

@router.get("/me")
async def get_current_user_info(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user information from token.
    
    This endpoint can be used to validate tokens and retrieve user details.
    
    Args:
        request: FastAPI request object
        db: Database session
    
    Returns:
        User information
    
    Raises:
        HTTPException: 401 if token is invalid
    """
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split(" ")[1]
    
    try:
        # Verify token
        payload = verify_token(token)
        
        # Extract user information
        user_id = UUID(payload["sub"])
        
        # Query user from database (SQLAlchemy 2.0)
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        return {
            "user_id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "timezone": user.timezone,
            "must_change_password": user.must_change_password,
            "created_at": user.created_at.isoformat(),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_user_info_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

@router.post("/logout")
async def logout(request: Request):
    """
    User logout endpoint.
    
    This endpoint is provided for consistency with frontend expectations.
    Since we use stateless JWT tokens, actual logout is handled client-side
    by removing the token from storage.
    
    Args:
        request: FastAPI request object
    
    Returns:
        Success message
    """
    logger.info("logout_requested", ip=request.client.host if request.client else "unknown")
    
    return {
        "message": "Logged out successfully",
        "detail": "Token should be removed from client storage"
    }

@router.post("/change-password")
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Change user password.
    
    Args:
        request: FastAPI request object
        password_data: Old and new password
        db: Database session
    
    Returns:
        Success message
    
    Raises:
        HTTPException: 401 if token is invalid or old password is incorrect
    """
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split(" ")[1]
    
    try:
        # Verify token
        payload = verify_token(token)
        user_id = UUID(payload["sub"])
        
        # Query user from database (SQLAlchemy 2.0)
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        
        # Verify old password
        from system_core.auth.password import hash_password
        if not verify_password(password_data.old_password, user.password_hash):
            logger.warning(
                "password_change_failed_invalid_old_password",
                user_id=str(user.id),
                username=user.username
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid old password",
            )
        
        # Update password
        user.password_hash = hash_password(password_data.new_password)
        user.must_change_password = False
        await db.commit()
        
        logger.info(
            "password_changed",
            user_id=str(user.id),
            username=user.username
        )
        
        return {
            "message": "Password changed successfully",
            "must_change_password": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("password_change_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password",
        )

