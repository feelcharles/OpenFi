"""
Event Serializer

Handles serialization and deserialization of events with support for
datetime, Decimal, UUID, and Enum types.
"""

import json
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from system_core.core.exceptions import EventBusError
from system_core.event_bus.models import Event

class EventSerializer:
    """
    Serializes and deserializes events to/from JSON.
    
    Supports special types:
    - datetime: ISO 8601 format
    - Decimal: string representation
    - UUID: string representation
    - Enum: enum value
    """
    
    def __init__(self, encoding: str = "utf-8"):
        """
        Initialize serializer.
        
        Args:
            encoding: Character encoding (default: utf-8)
        """
        self.encoding = encoding
    
    def serialize(self, event: Event) -> bytes:
        """
        Serialize event to JSON bytes.
        
        Args:
            event: Event object to serialize
            
        Returns:
            JSON bytes
            
        Raises:
            EventBusError: If serialization fails
        """
        try:
            # Convert event to dict
            event_dict = event.model_dump()
            
            # Serialize to JSON with custom encoder
            json_str = json.dumps(event_dict, cls=CustomJSONEncoder, ensure_ascii=False)
            
            # Encode to bytes
            return json_str.encode(self.encoding)
        
        except Exception as e:
            raise EventBusError(f"Failed to serialize event: {e}")
    
    def deserialize(self, data: bytes) -> Event:
        """
        Deserialize JSON bytes to event.
        
        Args:
            data: JSON bytes
            
        Returns:
            Event object
            
        Raises:
            EventBusError: If deserialization fails
        """
        try:
            # Decode bytes to string
            json_str = data.decode(self.encoding)
            
            # Parse JSON
            event_dict = json.loads(json_str, object_hook=self._decode_special_types)
            
            # Create Event object
            return Event(**event_dict)
        
        except Exception as e:
            raise EventBusError(f"Failed to deserialize event: {e}")
    
    def _decode_special_types(self, obj: dict) -> dict:
        """
        Decode special types from JSON.
        
        Args:
            obj: Dictionary from JSON
            
        Returns:
            Dictionary with decoded types
        """
        for key, value in obj.items():
            if isinstance(value, str):
                # Try to parse as datetime
                if self._is_iso_datetime(value):
                    try:
                        obj[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except ValueError:
                        pass
                
                # Try to parse as UUID
                elif self._is_uuid(value):
                    try:
                        obj[key] = UUID(value)
                    except ValueError:
                        pass
                
                # Try to parse as Decimal (only for specific keys that should be Decimal)
                # Don't convert schema_version or other string fields
                elif key not in ('schema_version', 'event_type', 'topic') and self._is_decimal(value):
                    try:
                        obj[key] = Decimal(value)
                    except (ValueError, TypeError):
                        pass
        
        return obj
    
    def _is_iso_datetime(self, value: str) -> bool:
        """Check if string looks like ISO 8601 datetime."""
        # Simple heuristic: contains 'T' and has date-like format
        return 'T' in value and len(value) >= 19
    
    def _is_uuid(self, value: str) -> bool:
        """Check if string looks like UUID."""
        # UUID format: 8-4-4-4-12 hex digits
        return len(value) == 36 and value.count('-') == 4
    
    def _is_decimal(self, value: str) -> bool:
        """Check if string looks like a decimal number."""
        # Check if it's a numeric string with decimal point
        try:
            float(value)
            return '.' in value
        except ValueError:
            return False

class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for special types.
    
    Handles:
    - datetime -> ISO 8601 string
    - Decimal -> string
    - UUID -> string
    - Enum -> value
    """
    
    def default(self, obj: Any) -> Any:
        """
        Encode special types.
        
        Args:
            obj: Object to encode
            
        Returns:
            JSON-serializable representation
        """
        if isinstance(obj, datetime):
            # Convert to ISO 8601 format
            return obj.isoformat()
        
        elif isinstance(obj, Decimal):
            # Convert to string to preserve precision
            return str(obj)
        
        elif isinstance(obj, UUID):
            # Convert to string
            return str(obj)
        
        elif isinstance(obj, Enum):
            # Use enum value
            return obj.value
        
        # Let the base class handle other types
        return super().default(obj)
