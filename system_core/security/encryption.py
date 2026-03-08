"""
Data encryption utilities.

Provides AES-256 encryption for sensitive data at rest.

Requirements: 42.4, 42.5
"""

import os
import base64
import hashlib
from typing import Optional, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

from system_core.config import get_logger, get_settings

logger = get_logger(__name__)

class SecretManager:
    """
    Secure secret management using environment variables or external service.
    
    Requirements: 42.5
    """
    
    def __init__(self):
        """Initialize secret manager."""
        self.settings = get_settings()
        self._encryption_key: Optional[bytes] = None
    
    def get_encryption_key(self) -> bytes:
        """
        Get or generate encryption key.
        
        Returns:
            Encryption key bytes
        """
        if self._encryption_key:
            return self._encryption_key
        
        # Try to get key from environment
        key_str = os.getenv("ENCRYPTION_KEY")
        
        if key_str:
            # Decode base64-encoded key
            try:
                self._encryption_key = base64.urlsafe_b64decode(key_str)
                logger.info("encryption_key_loaded_from_env")
                return self._encryption_key
            except Exception as e:
                logger.error("failed_to_decode_encryption_key", error=str(e))
        
        # Generate new key if not found
        logger.warning("generating_new_encryption_key")
        self._encryption_key = Fernet.generate_key()
        
        # Log warning to save the key
        encoded_key = base64.urlsafe_b64encode(self._encryption_key).decode()
        logger.warning(
            "save_encryption_key",
            message="Save this key to ENCRYPTION_KEY environment variable",
            key=encoded_key
        )
        
        return self._encryption_key
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get secret from environment variables.
        
        Args:
            key: Secret key name
            default: Default value if not found
        
        Returns:
            Secret value or default
        """
        value = os.getenv(key, default)
        
        if value is None:
            logger.warning("secret_not_found", key=key)
        
        return value
    
    def set_secret(self, key: str, value: str) -> None:
        """
        Set secret in environment (for testing only).
        
        Args:
            key: Secret key name
            value: Secret value
        """
        os.environ[key] = value
        logger.debug("secret_set", key=key)

# Global secret manager instance
_secret_manager: Optional[SecretManager] = None

def get_secret_manager() -> SecretManager:
    """Get global secret manager instance."""
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager

def derive_key(password: str, salt: bytes) -> bytes:
    """
    Derive encryption key from password using PBKDF2.
    
    Args:
        password: Password string
        salt: Salt bytes
    
    Returns:
        Derived key bytes
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits for AES-256
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def encrypt_data(data: str, key: Optional[bytes] = None) -> str:
    """
    Encrypt data using AES-256 (via Fernet).
    
    Args:
        data: Plain text data to encrypt
        key: Encryption key (uses default if not provided)
    
    Returns:
        Base64-encoded encrypted data
    
    Requirements: 42.4
    """
    if key is None:
        secret_manager = get_secret_manager()
        key = secret_manager.get_encryption_key()
    
    try:
        fernet = Fernet(key)
        encrypted = fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        logger.error("encryption_failed", error=str(e))
        raise ValueError(f"Failed to encrypt data: {str(e)}")

def decrypt_data(encrypted_data: str, key: Optional[bytes] = None) -> str:
    """
    Decrypt data using AES-256 (via Fernet).
    
    Args:
        encrypted_data: Base64-encoded encrypted data
        key: Encryption key (uses default if not provided)
    
    Returns:
        Decrypted plain text data
    
    Requirements: 42.4
    """
    if key is None:
        secret_manager = get_secret_manager()
        key = secret_manager.get_encryption_key()
    
    try:
        fernet = Fernet(key)
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data)
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception as e:
        logger.error("decryption_failed", error=str(e))
        raise ValueError(f"Failed to decrypt data: {str(e)}")

def hash_sensitive_data(data: str) -> str:
    """
    Hash sensitive data using SHA-256 (one-way).
    
    Use this for data that needs to be compared but not recovered.
    
    Args:
        data: Data to hash
    
    Returns:
        Hex-encoded hash
    """
    return hashlib.sha256(data.encode()).hexdigest()

def encrypt_dict(data: dict[str, Any], fields_to_encrypt: list) -> dict[str, Any]:
    """
    Encrypt specific fields in a dictionary.
    
    Args:
        data: Dictionary with data
        fields_to_encrypt: List of field names to encrypt
    
    Returns:
        Dictionary with encrypted fields
    """
    result = data.copy()
    
    for field in fields_to_encrypt:
        if field in result and result[field]:
            result[field] = encrypt_data(str(result[field]))
    
    return result

def decrypt_dict(data: dict[str, Any], fields_to_decrypt: list) -> dict[str, Any]:
    """
    Decrypt specific fields in a dictionary.
    
    Args:
        data: Dictionary with encrypted data
        fields_to_decrypt: List of field names to decrypt
    
    Returns:
        Dictionary with decrypted fields
    """
    result = data.copy()
    
    for field in fields_to_decrypt:
        if field in result and result[field]:
            try:
                result[field] = decrypt_data(result[field])
            except Exception as e:
                logger.error("field_decryption_failed", field=field, error=str(e))
                result[field] = None
    
    return result
