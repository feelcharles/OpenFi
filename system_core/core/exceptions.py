"""
Custom exception classes for OpenFi Lite.

Defines the exception hierarchy for different error types.
"""

class OpenFiError(Exception):
    """Base exception for all OpenFi Lite errors."""
    pass

class ConfigurationError(OpenFiError):
    """Raised when configuration is invalid or missing."""
    pass

class FetchError(OpenFiError):
    """Base exception for data fetching errors."""
    pass

class APITimeoutError(FetchError):
    """Raised when external API call times out."""
    pass

class APIAuthError(FetchError):
    """Raised when API authentication fails."""
    pass

class LLMError(OpenFiError):
    """Base exception for LLM-related errors."""
    pass

class LLMProviderError(LLMError):
    """Raised when LLM provider fails."""
    pass

class LLMRateLimitError(LLMError):
    """Raised when LLM rate limit is exceeded."""
    pass

class ExecutionError(OpenFiError):
    """Base exception for trading execution errors."""
    pass

class RiskLimitExceeded(ExecutionError):
    """Raised when risk limits are exceeded."""
    pass

class BrokerConnectionError(ExecutionError):
    """Raised when broker connection fails."""
    pass

class ValidationError(OpenFiError):
    """Raised when data validation fails."""
    pass

class DatabaseError(OpenFiError):
    """Raised when database operations fail."""
    pass

class EventBusError(OpenFiError):
    """Raised when event bus operations fail."""
    pass

class PermissionError(OpenFiError):
    """Raised when permission check fails."""
    pass

class AccessDeniedError(OpenFiError):
    """Raised when access to a resource is denied."""
    pass
