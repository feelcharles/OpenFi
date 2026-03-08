"""
Password hashing and verification using bcrypt.

This module provides secure password hashing with bcrypt
using a cost factor of 12 for enhanced security.
"""

from passlib.context import CryptContext
from system_core.config import get_logger

logger = get_logger(__name__)

# Password hashing context with bcrypt
# Cost factor 12 provides good security while maintaining reasonable performance
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Cost factor 12 as per requirements
)

class PasswordHasher:
    """
    Password hasher class for backward compatibility.
    
    Provides an object-oriented interface to password hashing functions.
    """
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt with cost factor 12.
        
        Args:
            password: Plain text password
        
        Returns:
            Hashed password string
        
        Raises:
            ValueError: If password is longer than 72 bytes
        """
        return hash_password(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hashed password.
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password from database
        
        Returns:
            True if password matches, False otherwise
        """
        return verify_password(plain_password, hashed_password)

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt with cost factor 12.
    
    Args:
        password: Plain text password
    
    Returns:
        Hashed password string
    
    Raises:
        ValueError: If password is longer than 72 bytes
    """
    # bcrypt has a 72 byte limit
    if len(password.encode('utf-8')) > 72:
        raise ValueError("Password cannot be longer than 72 bytes")
    
    hashed = pwd_context.hash(password)
    logger.debug("password_hashed")
    return hashed

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hashed password.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
    
    Returns:
        True if password matches, False otherwise
    """
    try:
        # Truncate password if too long (bcrypt limit)
        if len(plain_password.encode('utf-8')) > 72:
            plain_password = plain_password[:72]
        
        is_valid = pwd_context.verify(plain_password, hashed_password)
        logger.debug("password_verified", is_valid=is_valid)
        return is_valid
    except Exception as e:
        logger.error("password_verification_failed", error=str(e))
        return False

def needs_rehash(hashed_password: str) -> bool:
    """
    Check if password hash needs to be updated.
    
    This is useful when upgrading hashing algorithms or cost factors.
    
    Args:
        hashed_password: Hashed password from database
    
    Returns:
        True if hash should be updated, False otherwise
    """
    return pwd_context.needs_update(hashed_password)
