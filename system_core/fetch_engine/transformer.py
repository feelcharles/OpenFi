"""
Data Transformer

Transforms raw API responses to standardized format with quality scoring.

Validates: Requirements 23.2, 23.3, 23.4, 23.5, 23.6, 23.7
"""

import logging
from datetime import datetime
from typing import Any, Optional
from decimal import Decimal

from system_core.config import get_logger

logger = get_logger(__name__)

class DataTransformer:
    """
    Data transformation and quality scoring.
    
    Responsibilities:
    - Extract relevant fields from raw responses
    - Normalize data types
    - Validate required fields
    - Calculate quality scores
    - Enrich metadata
    """
    
    @staticmethod
    def extract_fields(raw_data: dict[str, Any], field_mapping: dict[str, str]) -> dict[str, Any]:
        """
        Extract relevant fields from raw API response.
        
        Args:
            raw_data: Raw API response
            field_mapping: Mapping of source fields to target fields
            
        Returns:
            Extracted fields dictionary
            
        Validates: Requirement 23.2
        """
        extracted = {}
        
        for target_field, source_field in field_mapping.items():
            # Support nested field access with dot notation
            value = raw_data
            for key in source_field.split('.'):
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    value = None
                    break
            
            if value is not None:
                extracted[target_field] = value
        
        return extracted
    
    @staticmethod
    def normalize_types(data: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize data types to standard formats.
        
        Conversions:
        - Timestamps to ISO 8601 strings
        - Prices to Decimal
        - Symbols to uppercase
        
        Args:
            data: Data dictionary
            
        Returns:
            Normalized data dictionary
            
        Validates: Requirement 23.3
        """
        normalized = {}
        
        for key, value in data.items():
            if value is None:
                normalized[key] = value
                continue
            
            # Normalize timestamps
            if isinstance(value, datetime):
                normalized[key] = value.isoformat()
            
            # Normalize prices (if key suggests it's a price)
            elif key in ['price', 'entry_price', 'stop_loss', 'take_profit', 'forecast', 'previous', 'actual']:
                try:
                    if isinstance(value, str):
                        # Remove currency symbols and commas
                        cleaned = value.replace('$', '').replace(',', '').strip()
                        if cleaned and cleaned != 'N/A':
                            normalized[key] = str(Decimal(cleaned))
                        else:
                            normalized[key] = None
                    elif isinstance(value, (int, float)):
                        normalized[key] = str(Decimal(str(value)))
                    else:
                        normalized[key] = value
                except (ValueError, TypeError):
                    normalized[key] = value
            
            # Normalize symbols to uppercase
            elif key in ['symbol', 'currency', 'country']:
                if isinstance(value, str):
                    normalized[key] = value.upper()
                else:
                    normalized[key] = value
            
            # Recursively normalize nested dictionaries
            elif isinstance(value, dict):
                normalized[key] = DataTransformer.normalize_types(value)
            
            # Normalize lists
            elif isinstance(value, list):
                normalized[key] = [
                    DataTransformer.normalize_types(item) if isinstance(item, dict) else item
                    for item in value
                ]
            
            else:
                normalized[key] = value
        
        return normalized
    
    @staticmethod
    def validate_schema(data: dict[str, Any], required_fields: list) -> bool:
        """
        Validate that required fields are present.
        
        Args:
            data: Data dictionary
            required_fields: List of required field names
            
        Returns:
            True if all required fields present
            
        Raises:
            ValueError: If required fields missing
            
        Validates: Requirement 23.4
        """
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
        
        return True
    
    @staticmethod
    def calculate_quality_score(data: dict[str, Any], metadata: dict[str, Any]) -> float:
        """
        Calculate data quality score (0-100).
        
        Factors:
        - Completeness: Percentage of non-null fields
        - Freshness: Age of data
        - Consistency: Data format consistency
        
        Args:
            data: Data dictionary
            metadata: Metadata dictionary
            
        Returns:
            Quality score (0-100)
            
        Validates: Requirement 23.5
        """
        score = 100.0
        
        # Completeness score (40% weight)
        total_fields = len(data)
        non_null_fields = sum(1 for v in data.values() if v is not None and v != '')
        completeness = (non_null_fields / total_fields * 100) if total_fields > 0 else 0
        completeness_score = completeness * 0.4
        
        # Freshness score (40% weight)
        fetch_time = metadata.get('fetch_time')
        data_timestamp = data.get('timestamp')
        
        if fetch_time and data_timestamp:
            try:
                if isinstance(fetch_time, str):
                    fetch_time = datetime.fromisoformat(fetch_time.replace('Z', '+00:00'))
                if isinstance(data_timestamp, str):
                    data_timestamp = datetime.fromisoformat(data_timestamp.replace('Z', '+00:00'))
                
                age_seconds = (fetch_time - data_timestamp).total_seconds()
                
                # Penalize old data
                if age_seconds < 300:  # < 5 minutes
                    freshness = 100
                elif age_seconds < 3600:  # < 1 hour
                    freshness = 90
                elif age_seconds < 86400:  # < 1 day
                    freshness = 70
                else:
                    freshness = 50
                
                freshness_score = freshness * 0.4
            except Exception:
                freshness_score = 20  # Default if can't calculate
        else:
            freshness_score = 20
        
        # Consistency score (20% weight)
        # Check if data types are consistent
        consistency = 100
        
        # Penalize if expected numeric fields are strings
        for key in ['price', 'volume', 'forecast', 'previous', 'actual']:
            if key in data and data[key] is not None:
                if not isinstance(data[key], (int, float, Decimal, str)):
                    consistency -= 10
        
        consistency_score = max(0, consistency) * 0.2
        
        # Total score
        total_score = completeness_score + freshness_score + consistency_score
        
        return round(min(100.0, max(0.0, total_score)), 2)
    
    @staticmethod
    def enrich_metadata(
        metadata: dict[str, Any],
        quality_score: float,
        source_version: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Enrich metadata with additional information.
        
        Args:
            metadata: Original metadata
            quality_score: Calculated quality score
            source_version: Optional source version
            
        Returns:
            Enriched metadata
            
        Validates: Requirement 23.6
        """
        enriched = {
            **metadata,
            "quality_score": quality_score,
            "fetch_time": datetime.utcnow().isoformat()
        }
        
        if source_version:
            enriched["source_version"] = source_version
        
        return enriched
    
    @staticmethod
    def should_discard(quality_score: float, threshold: float = 50.0) -> bool:
        """
        Determine if data should be discarded based on quality score.
        
        Args:
            quality_score: Quality score
            threshold: Minimum acceptable score
            
        Returns:
            True if should discard
            
        Validates: Requirement 23.7
        """
        if quality_score < threshold:
            logger.warning(
                f"Low quality data detected (score: {quality_score})",
                extra={"quality_score": quality_score, "threshold": threshold}
            )
            return True
        
        return False
    
    @staticmethod
    def transform(
        raw_data: dict[str, Any],
        field_mapping: dict[str, str],
        required_fields: list,
        metadata: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Complete transformation pipeline.
        
        Args:
            raw_data: Raw API response
            field_mapping: Field mapping dictionary
            required_fields: List of required fields
            metadata: Optional metadata
            
        Returns:
            Transformed and validated data
            
        Raises:
            ValueError: If validation fails or quality too low
        """
        # Extract fields
        extracted = DataTransformer.extract_fields(raw_data, field_mapping)
        
        # Normalize types
        normalized = DataTransformer.normalize_types(extracted)
        
        # Validate schema
        DataTransformer.validate_schema(normalized, required_fields)
        
        # Calculate quality score
        metadata = metadata or {}
        quality_score = DataTransformer.calculate_quality_score(normalized, metadata)
        
        # Check if should discard
        if DataTransformer.should_discard(quality_score):
            raise ValueError(f"Data quality too low: {quality_score}")
        
        # Enrich metadata
        enriched_metadata = DataTransformer.enrich_metadata(metadata, quality_score)
        
        return {
            "data": normalized,
            "metadata": enriched_metadata
        }
