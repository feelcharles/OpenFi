"""
Encrypted SQLAlchemy Types

Provides automatic encryption/decryption for sensitive database fields.
Uses AES-256 encryption transparently at the ORM level.

Requirements: 42.4, 42.5
"""

import json
import logging
from typing import Any, Optional

from sqlalchemy import String, Text
from sqlalchemy.types import TypeDecorator

from system_core.security.encryption import encrypt_data, decrypt_data

logger = logging.getLogger(__name__)

class EncryptedString(TypeDecorator):
    """
    Encrypted string type for SQLAlchemy.
    
    Automatically encrypts data on write and decrypts on read.
    Stores encrypted data as TEXT in database.
    
    Usage:
        class User(Base):
            api_key = Column(EncryptedString(255))
    """
    
    impl = Text
    cache_ok = True
    
    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """
        Encrypt value before storing in database.
        
        Args:
            value: Plain text value
            dialect: SQLAlchemy dialect
        
        Returns:
            Encrypted value or None
        """
        if value is not None:
            try:
                encrypted = encrypt_data(value)
                logger.debug("Encrypted string field for database storage")
                return encrypted
            except Exception as e:
                logger.error(f"Failed to encrypt string: {e}")
                raise ValueError(f"Encryption failed: {e}")
        return None
    
    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """
        Decrypt value after reading from database.
        
        Args:
            value: Encrypted value from database
            dialect: SQLAlchemy dialect
        
        Returns:
            Decrypted plain text or None
        """
        if value is not None:
            try:
                decrypted = decrypt_data(value)
                logger.debug("Decrypted string field from database")
                return decrypted
            except Exception as e:
                logger.error(f"Failed to decrypt string: {e}")
                # Return None instead of raising to prevent data loss
                return None
        return None

class EncryptedJSON(TypeDecorator):
    """
    Encrypted JSON type for SQLAlchemy.
    
    Automatically encrypts JSON data on write and decrypts on read.
    Useful for storing credentials, API keys, and other sensitive structured data.
    
    Usage:
        class Broker(Base):
            credentials = Column(EncryptedJSON)
    """
    
    impl = Text
    cache_ok = True
    
    def process_bind_param(self, value: Optional[dict], dialect) -> Optional[str]:
        """
        Encrypt JSON value before storing in database.
        
        Args:
            value: Dictionary to encrypt
            dialect: SQLAlchemy dialect
        
        Returns:
            Encrypted JSON string or None
        """
        if value is not None:
            try:
                # Convert dict to JSON string
                json_str = json.dumps(value, ensure_ascii=False)
                # Encrypt JSON string
                encrypted = encrypt_data(json_str)
                logger.debug("Encrypted JSON field for database storage")
                return encrypted
            except Exception as e:
                logger.error(f"Failed to encrypt JSON: {e}")
                raise ValueError(f"JSON encryption failed: {e}")
        return None
    
    def process_result_value(self, value: Optional[str], dialect) -> Optional[dict]:
        """
        Decrypt JSON value after reading from database.
        
        Args:
            value: Encrypted JSON string from database
            dialect: SQLAlchemy dialect
        
        Returns:
            Decrypted dictionary or None
        """
        if value is not None:
            try:
                # Decrypt JSON string
                decrypted_str = decrypt_data(value)
                # Parse JSON
                decrypted_dict = json.loads(decrypted_str)
                logger.debug("Decrypted JSON field from database")
                return decrypted_dict
            except Exception as e:
                logger.error(f"Failed to decrypt JSON: {e}")
                # Return empty dict instead of raising to prevent data loss
                return {}
        return None

class EncryptedText(TypeDecorator):
    """
    Encrypted text type for SQLAlchemy (for longer text fields).
    
    Similar to EncryptedString but for TEXT columns.
    
    Usage:
        class Config(Base):
            private_notes = Column(EncryptedText)
    """
    
    impl = Text
    cache_ok = True
    
    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """Encrypt text before storing."""
        if value is not None:
            try:
                encrypted = encrypt_data(value)
                logger.debug("Encrypted text field for database storage")
                return encrypted
            except Exception as e:
                logger.error(f"Failed to encrypt text: {e}")
                raise ValueError(f"Text encryption failed: {e}")
        return None
    
    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """Decrypt text after reading."""
        if value is not None:
            try:
                decrypted = decrypt_data(value)
                logger.debug("Decrypted text field from database")
                return decrypted
            except Exception as e:
                logger.error(f"Failed to decrypt text: {e}")
                return None
        return None

# Utility function for migrating existing data
def encrypt_existing_field(
    session,
    model_class,
    field_name: str,
    batch_size: int = 100
) -> int:
    """
    Encrypt existing unencrypted data in a database field.
    
    Use this for migrating existing databases to use encrypted fields.
    
    Args:
        session: SQLAlchemy session
        model_class: Model class containing the field
        field_name: Name of field to encrypt
        batch_size: Number of records to process per batch
    
    Returns:
        Number of records encrypted
    
    Example:
        from system_core.database.models import Broker
        from system_core.database import get_db_client
        
        session = next(get_db_client())
        count = encrypt_existing_field(session, Broker, 'credentials')
        print(f"Encrypted {count} records")
    """
    from sqlalchemy import inspect
    
    encrypted_count = 0
    
    try:
        # Get all records
        records = session.query(model_class).all()
        
        for record in records:
            # Get current value
            current_value = getattr(record, field_name)
            
            if current_value is not None:
                # Check if already encrypted (basic heuristic)
                if not isinstance(current_value, str) or not current_value.startswith('gAAAAA'):
                    # Encrypt the value
                    if isinstance(current_value, dict):
                        # JSON field
                        json_str = json.dumps(current_value)
                        encrypted = encrypt_data(json_str)
                    else:
                        # String field
                        encrypted = encrypt_data(str(current_value))
                    
                    # Update record
                    setattr(record, field_name, encrypted)
                    encrypted_count += 1
                    
                    # Commit in batches
                    if encrypted_count % batch_size == 0:
                        session.commit()
                        logger.info(f"Encrypted {encrypted_count} records so far...")
        
        # Final commit
        session.commit()
        logger.info(f"Successfully encrypted {encrypted_count} records")
        
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to encrypt existing data: {e}")
        raise
    
    return encrypted_count

__all__ = [
    'EncryptedString',
    'EncryptedJSON',
    'EncryptedText',
    'encrypt_existing_field',
]
