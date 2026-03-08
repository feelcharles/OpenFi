"""
JWT token generation and validation using RS256 algorithm.

This module handles JWT token creation, validation, and refresh operations
using RSA public/private key pairs for enhanced security.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Any
from pathlib import Path

import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError

from system_core.config import get_logger

logger = get_logger(__name__)

class JWTHandler:
    """
    JWT token handler using RS256 algorithm.
    
    Manages JWT token generation, validation, and refresh operations
    with RSA public/private key pairs.
    """
    
    def __init__(
        self,
        private_key_path: Optional[str] = None,
        public_key_path: Optional[str] = None,
        algorithm: str = "RS256",
        issuer: str = "OpenFi-lite",
        token_expiration_hours: int = 24
    ):
        """
        Initialize JWT handler.
        
        Args:
            private_key_path: Path to RSA private key file (PEM format)
            public_key_path: Path to RSA public key file (PEM format)
            algorithm: JWT algorithm (default: RS256)
            issuer: Token issuer identifier
            token_expiration_hours: Token expiration time in hours
        """
        self.algorithm = algorithm
        self.issuer = issuer
        self.token_expiration_hours = token_expiration_hours
        
        # Load keys from environment or default paths
        self.private_key_path = private_key_path or os.getenv(
            "JWT_PRIVATE_KEY_PATH",
            "config/keys/jwt_private.pem"
        )
        self.public_key_path = public_key_path or os.getenv(
            "JWT_PUBLIC_KEY_PATH",
            "config/keys/jwt_public.pem"
        )
        
        # Load keys
        self.private_key = self._load_private_key()
        self.public_key = self._load_public_key()
        
        logger.info(
            "jwt_handler_initialized",
            algorithm=self.algorithm,
            issuer=self.issuer,
            expiration_hours=self.token_expiration_hours
        )
    
    def _load_private_key(self) -> str:
        """Load RSA private key from file."""
        try:
            key_path = Path(self.private_key_path)
            
            # Use file lock to prevent race condition
            lock_path = key_path.parent / ".jwt_key.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Acquire lock before checking/generating keys
            import fcntl
            with open(lock_path, 'w') as lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                    
                    if not key_path.exists():
                        logger.warning(
                            "private_key_not_found",
                            path=str(key_path),
                            message="Generating new RSA key pair"
                        )
                        self._generate_key_pair()
                    
                    with open(key_path, "r") as f:
                        private_key = f.read()
                    
                    logger.info("private_key_loaded", path=str(key_path))
                    return private_key
                    
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            
        except ImportError:
            # fcntl not available on Windows, fallback to simple check
            logger.warning("fcntl_not_available", message="File locking not supported on this platform")
            
            if not key_path.exists():
                logger.warning(
                    "private_key_not_found",
                    path=str(key_path),
                    message="Generating new RSA key pair"
                )
                self._generate_key_pair()
            
            with open(key_path, "r") as f:
                private_key = f.read()
            
            logger.info("private_key_loaded", path=str(key_path))
            return private_key
            
        except Exception as e:
            logger.error("failed_to_load_private_key", error=str(e))
            raise
    
    def _load_public_key(self) -> str:
        """Load RSA public key from file."""
        try:
            key_path = Path(self.public_key_path)
            if not key_path.exists():
                raise FileNotFoundError(f"Public key not found: {key_path}")
            
            with open(key_path, "r") as f:
                public_key = f.read()
            
            logger.info("public_key_loaded", path=str(key_path))
            return public_key
            
        except Exception as e:
            logger.error("failed_to_load_public_key", error=str(e))
            raise
    
    def _generate_key_pair(self) -> None:
        """Generate RSA key pair if not exists."""
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Generate public key
        public_key = private_key.public_key()
        
        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Create keys directory if not exists
        keys_dir = Path(self.private_key_path).parent
        keys_dir.mkdir(parents=True, exist_ok=True)
        
        # Write keys to files
        with open(self.private_key_path, "wb") as f:
            f.write(private_pem)
        
        with open(self.public_key_path, "wb") as f:
            f.write(public_pem)
        
        logger.info(
            "rsa_key_pair_generated",
            private_key_path=self.private_key_path,
            public_key_path=self.public_key_path
        )
    
    def create_token(
        self,
        user_id: str,
        username: str,
        role: str,
        additional_claims: Optional[dict[str, Any]] = None
    ) -> str:
        """
        Create JWT access token.
        
        Args:
            user_id: User UUID
            username: Username
            role: User role (admin, trader, viewer)
            additional_claims: Additional claims to include in token
        
        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        expiration = now + timedelta(hours=self.token_expiration_hours)
        
        payload = {
            "sub": user_id,
            "username": username,
            "role": role,
            "iss": self.issuer,
            "iat": now,
            "exp": expiration,
        }
        
        # Add additional claims if provided
        if additional_claims:
            payload.update(additional_claims)
        
        try:
            token = jwt.encode(
                payload,
                self.private_key,
                algorithm=self.algorithm
            )
            
            logger.info(
                "jwt_token_created",
                user_id=user_id,
                username=username,
                role=role,
                expiration=expiration.isoformat()
            )
            
            return token
            
        except Exception as e:
            logger.error(
                "jwt_token_creation_failed",
                user_id=user_id,
                error=str(e)
            )
            raise
    
    def create_access_token(self, data: dict) -> str:
        """
        Create JWT access token (simplified interface for backward compatibility).
        
        Args:
            data: Dictionary containing at minimum 'sub' (user_id)
        
        Returns:
            JWT token string
        """
        user_id = data.get("sub", "unknown")
        username = data.get("username", user_id)
        role = data.get("role", "viewer")
        
        # Extract additional claims
        additional_claims = {
            k: v for k, v in data.items()
            if k not in ["sub", "username", "role"]
        }
        
        return self.create_token(user_id, username, role, additional_claims)
    
    def decode_token(self, token: str) -> dict[str, Any]:
        """
        Decode JWT token (alias for verify_token for backward compatibility).
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded token payload
        """
        return self.verify_token(token)
    
    def verify_token(self, token: str) -> dict[str, Any]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded token payload
        
        Raises:
            InvalidTokenError: If token is invalid
            ExpiredSignatureError: If token is expired
        """
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.algorithm],
                issuer=self.issuer
            )
            
            logger.debug(
                "jwt_token_verified",
                user_id=payload.get("sub"),
                username=payload.get("username")
            )
            
            return payload
            
        except ExpiredSignatureError:
            logger.warning("jwt_token_expired", token=token[:20] + "...")
            raise
        except InvalidTokenError as e:
            logger.warning("jwt_token_invalid", error=str(e))
            raise
    
    def refresh_token(self, token: str) -> str:
        """
        Refresh JWT token with extended expiration.
        
        Args:
            token: Current valid JWT token
        
        Returns:
            New JWT token with extended expiration
        
        Raises:
            InvalidTokenError: If token is invalid
        """
        try:
            # Verify current token
            payload = self.verify_token(token)
            
            # Create new token with same claims but extended expiration
            new_token = self.create_token(
                user_id=payload["sub"],
                username=payload["username"],
                role=payload["role"],
                additional_claims={
                    k: v for k, v in payload.items()
                    if k not in ["sub", "username", "role", "iss", "iat", "exp"]
                }
            )
            
            logger.info(
                "jwt_token_refreshed",
                user_id=payload["sub"],
                username=payload["username"]
            )
            
            return new_token
            
        except Exception as e:
            logger.error("jwt_token_refresh_failed", error=str(e))
            raise

# Global JWT handler instance
_jwt_handler: Optional[JWTHandler] = None

def get_jwt_handler() -> JWTHandler:
    """Get or create global JWT handler instance."""
    global _jwt_handler
    if _jwt_handler is None:
        _jwt_handler = JWTHandler()
    return _jwt_handler

def create_access_token(
    user_id: str,
    username: str,
    role: str,
    additional_claims: Optional[dict[str, Any]] = None
) -> str:
    """
    Create JWT access token (convenience function).
    
    Args:
        user_id: User UUID
        username: Username
        role: User role
        additional_claims: Additional claims
    
    Returns:
        JWT token string
    """
    handler = get_jwt_handler()
    return handler.create_token(user_id, username, role, additional_claims)

def verify_token(token: str) -> dict[str, Any]:
    """
    Verify JWT token (convenience function).
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload
    """
    handler = get_jwt_handler()
    return handler.verify_token(token)
