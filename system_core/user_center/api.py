"""
User Center API endpoints.

This module provides FastAPI routes for user and EA profile management:
- POST /api/users - Create user
- GET /api/users/{id} - Get user
- PUT /api/users/{id} - Update user
- DELETE /api/users/{id} - Delete user
- POST /api/ea-profiles - Create EA profile
- GET /api/ea-profiles/{id} - Get EA profile
- PUT /api/ea-profiles/{id} - Update EA profile
- DELETE /api/ea-profiles/{id} - Delete EA profile
- GET /api/ea-profiles?user_id={id} - List user's EA profiles
- GET /api/users/{id}/config - Get complete user configuration
"""

from typing import AsyncGenerator, Optional
from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from system_core.auth.middleware import get_current_user, CurrentUser, require_admin
from system_core.auth.password import hash_password
from system_core.database.models import User, EAProfile
from system_core.config import get_logger

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["user_center"])

# Dependency to get database session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    from system_core.database.client import get_db_client
    db_client = get_db_client()
    async with db_client.session() as session:
        yield session

# Request/Response models for User
class UserCreate(BaseModel):
    """User creation request."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8)
    role: str = Field(default="trader", pattern="^(admin|trader|viewer)$")
    timezone: str = Field(default="Asia/Shanghai")

class UserUpdate(BaseModel):
    """User update request."""
    email: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=8)
    role: Optional[str] = Field(None, pattern="^(admin|trader|viewer)$")
    timezone: Optional[str] = None

class UserResponse(BaseModel):
    """User response."""
    id: str
    username: str
    email: str
    role: str
    timezone: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

# Request/Response models for EA Profile
class EAProfileCreate(BaseModel):
    """EA profile creation request."""
    user_id: UUID
    ea_name: str = Field(..., min_length=1, max_length=100)
    symbols: list[str] = Field(..., min_items=1)
    timeframe: str = Field(..., pattern="^(M1|M5|M15|M30|H1|H4|D1|W1|MN1)$")
    risk_per_trade: Decimal = Field(..., ge=0.0001, le=1.0)
    max_positions: int = Field(..., ge=1, le=100)
    max_total_risk: Decimal = Field(default=Decimal("0.1"), ge=0.0001, le=1.0)
    strategy_logic_description: Optional[str] = None
    auto_execution: bool = Field(default=False)

    @validator('symbols')
    def validate_symbols(cls, v):
        """Validate symbols are uppercase."""
        return [s.upper() for s in v]

class EAProfileUpdate(BaseModel):
    """EA profile update request."""
    ea_name: Optional[str] = Field(None, min_length=1, max_length=100)
    symbols: Optional[list[str]] = Field(None, min_items=1)
    timeframe: Optional[str] = Field(None, pattern="^(M1|M5|M15|M30|H1|H4|D1|W1|MN1)$")
    risk_per_trade: Optional[Decimal] = Field(None, ge=0.0001, le=1.0)
    max_positions: Optional[int] = Field(None, ge=1, le=100)
    max_total_risk: Optional[Decimal] = Field(None, ge=0.0001, le=1.0)
    strategy_logic_description: Optional[str] = None
    auto_execution: Optional[bool] = None

    @validator('symbols')
    def validate_symbols(cls, v):
        """Validate symbols are uppercase."""
        if v is not None:
            return [s.upper() for s in v]
        return v

class EAProfileResponse(BaseModel):
    """EA profile response."""
    id: str
    user_id: str
    ea_name: str
    symbols: list[str]
    timeframe: str
    risk_per_trade: str
    max_positions: int
    max_total_risk: str
    strategy_logic_description: Optional[str]
    auto_execution: bool
    version: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

class UserConfigResponse(BaseModel):
    """Complete user configuration response."""
    user: UserResponse
    ea_profiles: list[EAProfileResponse]

# ============================================
# User Management Endpoints
# ============================================

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Create a new user.
    
    Requires admin role.
    
    Args:
        user_data: User creation data
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        Created user information
    
    Raises:
        HTTPException: 400 if username or email already exists
        HTTPException: 401 if not authenticated
        HTTPException: 403 if not admin
    """
    try:
        # Check if username already exists
        result = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        # Check if email already exists
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
        
        # Hash password
        password_hash = hash_password(user_data.password)
        
        # Create user
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=password_hash,
            role=user_data.role,
            timezone=user_data.timezone
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logger.info(
            "user_created",
            user_id=str(new_user.id),
            username=new_user.username,
            role=new_user.role,
            created_by=str(current_user.user_id)
        )
        
        return UserResponse(
            id=str(new_user.id),
            username=new_user.username,
            email=new_user.email,
            role=new_user.role,
            timezone=new_user.timezone,
            created_at=new_user.created_at.isoformat(),
            updated_at=new_user.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_user_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Get user by ID.
    
    Users can only view their own profile unless they are admin.
    
    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        User information
    
    Raises:
        HTTPException: 403 if trying to access another user's profile
        HTTPException: 404 if user not found
    """
    try:
        # Check permissions
        if str(user_id) != str(current_user.user_id) and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access other user's profile"
            )
        
        # Query user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            role=user.role,
            timezone=user.timezone,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_user_error", user_id=str(user_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Update user information.
    
    Users can only update their own profile unless they are admin.
    Only admin can change roles.
    
    Args:
        user_id: User ID
        user_data: User update data
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        Updated user information
    
    Raises:
        HTTPException: 403 if trying to update another user's profile
        HTTPException: 404 if user not found
    """
    try:
        # Check permissions
        if str(user_id) != str(current_user.user_id) and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update other user's profile"
            )
        
        # Query user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update fields
        if user_data.email is not None:
            # Check if email already exists
            result = await db.execute(
                select(User).where(User.email == user_data.email, User.id != user_id)
            )
            if result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
            user.email = user_data.email
        
        if user_data.password is not None:
            user.password_hash = hash_password(user_data.password)
        
        if user_data.role is not None:
            # Only admin can change roles
            if current_user.role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only admin can change user roles"
                )
            user.role = user_data.role
        
        if user_data.timezone is not None:
            user.timezone = user_data.timezone
        
        await db.commit()
        await db.refresh(user)
        
        logger.info(
            "user_updated",
            user_id=str(user.id),
            updated_by=str(current_user.user_id)
        )
        
        return UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            role=user.role,
            timezone=user.timezone,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_user_error", user_id=str(user_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Delete user.
    
    Requires admin role.
    Cascades to delete all related EA profiles, trades, etc.
    
    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        Success message
    
    Raises:
        HTTPException: 404 if user not found
    """
    try:
        # Query user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Delete user (cascades to related records)
        await db.delete(user)
        await db.commit()
        
        logger.info(
            "user_deleted",
            user_id=str(user_id),
            deleted_by=str(current_user.user_id)
        )
        
        return {"message": "User deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_user_error", user_id=str(user_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# ============================================
# EA Profile Management Endpoints
# ============================================

@router.post("/ea-profiles", response_model=EAProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_ea_profile(
    profile_data: EAProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Create a new EA profile.
    
    Users can only create profiles for themselves unless they are admin.
    
    Args:
        profile_data: EA profile creation data
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        Created EA profile information
    
    Raises:
        HTTPException: 403 if trying to create profile for another user
        HTTPException: 400 if validation fails
    """
    try:
        # Check permissions
        if str(profile_data.user_id) != str(current_user.user_id) and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create EA profile for another user"
            )
        
        # Verify user exists
        result = await db.execute(
            select(User).where(User.id == profile_data.user_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User not found"
            )
        
        # Create EA profile
        new_profile = EAProfile(
            user_id=profile_data.user_id,
            ea_name=profile_data.ea_name,
            symbols=profile_data.symbols,
            timeframe=profile_data.timeframe,
            risk_per_trade=profile_data.risk_per_trade,
            max_positions=profile_data.max_positions,
            max_total_risk=profile_data.max_total_risk,
            strategy_logic_description=profile_data.strategy_logic_description,
            auto_execution=profile_data.auto_execution
        )
        
        db.add(new_profile)
        await db.commit()
        await db.refresh(new_profile)
        
        logger.info(
            "ea_profile_created",
            profile_id=str(new_profile.id),
            ea_name=new_profile.ea_name,
            user_id=str(new_profile.user_id),
            created_by=str(current_user.user_id)
        )
        
        return EAProfileResponse(
            id=str(new_profile.id),
            user_id=str(new_profile.user_id),
            ea_name=new_profile.ea_name,
            symbols=new_profile.symbols,
            timeframe=new_profile.timeframe,
            risk_per_trade=str(new_profile.risk_per_trade),
            max_positions=new_profile.max_positions,
            max_total_risk=str(new_profile.max_total_risk),
            strategy_logic_description=new_profile.strategy_logic_description,
            auto_execution=new_profile.auto_execution,
            version=new_profile.version,
            created_at=new_profile.created_at.isoformat(),
            updated_at=new_profile.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_ea_profile_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/ea-profiles/{profile_id}", response_model=EAProfileResponse)
async def get_ea_profile(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Get EA profile by ID.
    
    Users can only view their own profiles unless they are admin.
    
    Args:
        profile_id: EA profile ID
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        EA profile information
    
    Raises:
        HTTPException: 403 if trying to access another user's profile
        HTTPException: 404 if profile not found
    """
    try:
        # Query profile
        result = await db.execute(
            select(EAProfile).where(EAProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="EA profile not found"
            )
        
        # Check permissions
        if str(profile.user_id) != str(current_user.user_id) and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access other user's EA profile"
            )
        
        return EAProfileResponse(
            id=str(profile.id),
            user_id=str(profile.user_id),
            ea_name=profile.ea_name,
            symbols=profile.symbols,
            timeframe=profile.timeframe,
            risk_per_trade=str(profile.risk_per_trade),
            max_positions=profile.max_positions,
            max_total_risk=str(profile.max_total_risk),
            strategy_logic_description=profile.strategy_logic_description,
            auto_execution=profile.auto_execution,
            version=profile.version,
            created_at=profile.created_at.isoformat(),
            updated_at=profile.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_ea_profile_error", profile_id=str(profile_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.put("/ea-profiles/{profile_id}", response_model=EAProfileResponse)
async def update_ea_profile(
    profile_id: UUID,
    profile_data: EAProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Update EA profile.
    
    Users can only update their own profiles unless they are admin.
    
    Args:
        profile_id: EA profile ID
        profile_data: EA profile update data
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        Updated EA profile information
    
    Raises:
        HTTPException: 403 if trying to update another user's profile
        HTTPException: 404 if profile not found
    """
    try:
        # Query profile
        result = await db.execute(
            select(EAProfile).where(EAProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="EA profile not found"
            )
        
        # Check permissions
        if str(profile.user_id) != str(current_user.user_id) and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update other user's EA profile"
            )
        
        # Update fields
        if profile_data.ea_name is not None:
            profile.ea_name = profile_data.ea_name
        if profile_data.symbols is not None:
            profile.symbols = profile_data.symbols
        if profile_data.timeframe is not None:
            profile.timeframe = profile_data.timeframe
        if profile_data.risk_per_trade is not None:
            profile.risk_per_trade = profile_data.risk_per_trade
        if profile_data.max_positions is not None:
            profile.max_positions = profile_data.max_positions
        if profile_data.max_total_risk is not None:
            profile.max_total_risk = profile_data.max_total_risk
        if profile_data.strategy_logic_description is not None:
            profile.strategy_logic_description = profile_data.strategy_logic_description
        if profile_data.auto_execution is not None:
            profile.auto_execution = profile_data.auto_execution
        
        await db.commit()
        await db.refresh(profile)
        
        logger.info(
            "ea_profile_updated",
            profile_id=str(profile.id),
            updated_by=str(current_user.user_id)
        )
        
        return EAProfileResponse(
            id=str(profile.id),
            user_id=str(profile.user_id),
            ea_name=profile.ea_name,
            symbols=profile.symbols,
            timeframe=profile.timeframe,
            risk_per_trade=str(profile.risk_per_trade),
            max_positions=profile.max_positions,
            max_total_risk=str(profile.max_total_risk),
            strategy_logic_description=profile.strategy_logic_description,
            auto_execution=profile.auto_execution,
            version=profile.version,
            created_at=profile.created_at.isoformat(),
            updated_at=profile.updated_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_ea_profile_error", profile_id=str(profile_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.delete("/ea-profiles/{profile_id}", status_code=status.HTTP_200_OK)
async def delete_ea_profile(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Delete EA profile.
    
    Users can only delete their own profiles unless they are admin.
    
    Args:
        profile_id: EA profile ID
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        Success message
    
    Raises:
        HTTPException: 403 if trying to delete another user's profile
        HTTPException: 404 if profile not found
    """
    try:
        # Query profile
        result = await db.execute(
            select(EAProfile).where(EAProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="EA profile not found"
            )
        
        # Check permissions
        if str(profile.user_id) != str(current_user.user_id) and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete other user's EA profile"
            )
        
        # Delete profile
        await db.delete(profile)
        await db.commit()
        
        logger.info(
            "ea_profile_deleted",
            profile_id=str(profile_id),
            deleted_by=str(current_user.user_id)
        )
        
        return {"message": "EA profile deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_ea_profile_error", profile_id=str(profile_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/ea-profiles", response_model=list[EAProfileResponse])
async def list_ea_profiles(
    user_id: UUID = Query(..., description="User ID to filter EA profiles"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    List EA profiles for a user.
    
    Users can only list their own profiles unless they are admin.
    
    Args:
        user_id: User ID to filter profiles
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        List of EA profiles
    
    Raises:
        HTTPException: 403 if trying to list another user's profiles
    """
    try:
        # Check permissions
        if str(user_id) != str(current_user.user_id) and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot list other user's EA profiles"
            )
        
        # Query profiles
        result = await db.execute(
            select(EAProfile).where(EAProfile.user_id == user_id)
        )
        profiles = result.scalars().all()
        
        return [
            EAProfileResponse(
                id=str(profile.id),
                user_id=str(profile.user_id),
                ea_name=profile.ea_name,
                symbols=profile.symbols,
                timeframe=profile.timeframe,
                risk_per_trade=str(profile.risk_per_trade),
                max_positions=profile.max_positions,
                max_total_risk=str(profile.max_total_risk),
                strategy_logic_description=profile.strategy_logic_description,
                auto_execution=profile.auto_execution,
                version=profile.version,
                created_at=profile.created_at.isoformat(),
                updated_at=profile.updated_at.isoformat()
            )
            for profile in profiles
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("list_ea_profiles_error", user_id=str(user_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/users/{user_id}/config", response_model=UserConfigResponse)
async def get_user_config(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Get complete user configuration including all EA profiles.
    
    Response time target: under 100ms.
    Users can only view their own config unless they are admin.
    
    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        Complete user configuration with EA profiles
    
    Raises:
        HTTPException: 403 if trying to access another user's config
        HTTPException: 404 if user not found
    """
    try:
        # Check permissions
        if str(user_id) != str(current_user.user_id) and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access other user's configuration"
            )
        
        # Query user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Query EA profiles
        result = await db.execute(
            select(EAProfile).where(EAProfile.user_id == user_id)
        )
        profiles = result.scalars().all()
        
        return UserConfigResponse(
            user=UserResponse(
                id=str(user.id),
                username=user.username,
                email=user.email,
                role=user.role,
                timezone=user.timezone,
                created_at=user.created_at.isoformat(),
                updated_at=user.updated_at.isoformat()
            ),
            ea_profiles=[
                EAProfileResponse(
                    id=str(profile.id),
                    user_id=str(profile.user_id),
                    ea_name=profile.ea_name,
                    symbols=profile.symbols,
                    timeframe=profile.timeframe,
                    risk_per_trade=str(profile.risk_per_trade),
                    max_positions=profile.max_positions,
                    max_total_risk=str(profile.max_total_risk),
                    strategy_logic_description=profile.strategy_logic_description,
                    auto_execution=profile.auto_execution,
                    version=profile.version,
                    created_at=profile.created_at.isoformat(),
                    updated_at=profile.updated_at.isoformat()
                )
                for profile in profiles
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_user_config_error", user_id=str(user_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# ============================================
# Health Check Endpoint
# ============================================

@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint.
    
    This endpoint does not require authentication.
    
    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "user_center"
    }
