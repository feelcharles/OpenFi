"""
Authentication and authorization module for OpenFi Lite.

This module provides JWT-based authentication, role-based access control,
password hashing, and rate limiting for API endpoints.
"""

from .jwt_handler import JWTHandler, create_access_token, verify_token
from .middleware import get_current_user, require_role, require_admin, require_trader
from .rbac import Role, check_permission, RBACManager, require_permission
from .rate_limiter import RateLimiter, check_rate_limit
from .password import hash_password, verify_password, PasswordHasher
from .api import router as auth_router

__all__ = [
    "JWTHandler",
    "create_access_token",
    "verify_token",
    "get_current_user",
    "require_role",
    "require_admin",
    "require_trader",
    "Role",
    "check_permission",
    "require_permission",
    "RBACManager",
    "RateLimiter",
    "check_rate_limit",
    "hash_password",
    "verify_password",
    "PasswordHasher",
    "auth_router",
]
