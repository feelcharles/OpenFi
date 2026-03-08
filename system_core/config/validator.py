"""
Configuration file validator.

Validates YAML configuration files using Pydantic models.
Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5, 11.6
"""

import sys
from pathlib import Path
from typing import Any, Optional
import yaml
from pydantic import BaseModel, Field, field_validator, ValidationError
from croniter import croniter

from system_core.config.logging_config import get_logger

logger = get_logger(__name__)

class ScheduleConfig(BaseModel):
    """Schedule configuration model."""
    cron: Optional[str] = None
    seconds: Optional[int] = None
    
    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: Optional[str]) -> Optional[str]:
        """Validate cron expression syntax."""
        if v is not None and not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v}")
        return v

class DataSourceConfig(BaseModel):
    """Data source configuration model."""
    source_id: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)
    api_endpoint: str = Field(..., min_length=1)
    credentials: dict[str, str] = Field(default_factory=dict)
    schedule_type: str = Field(..., pattern="^(cron|interval)$")
    schedule_config: ScheduleConfig
    enabled: bool = Field(default=True)
    retry_count: int = Field(default=3, ge=0)
    timeout: int = Field(default=30, ge=1)
    parameters: Optional[dict[str, Any]] = None
    
    @field_validator("api_endpoint")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"Invalid URL format: {v}")
        return v
    
    @field_validator("credentials")
    @classmethod
    def validate_credentials(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate that API keys are non-empty."""
        for key, value in v.items():
            if "key" in key.lower() and not value:
                raise ValueError(f"API key '{key}' cannot be empty")
        return v

class FetchSourcesConfig(BaseModel):
    """Fetch sources configuration model."""
    sources: list[DataSourceConfig]

class LLMModelConfig(BaseModel):
    """LLM model configuration."""
    name: str = Field(..., min_length=1)
    max_tokens: int = Field(..., ge=1)
    temperature: float = Field(..., ge=0.0, le=2.0)
    context_window: Optional[int] = Field(default=None, ge=1)

class RateLimitConfig(BaseModel):
    """Rate limit configuration."""
    requests_per_minute: int = Field(..., ge=1)
    tokens_per_minute: Optional[int] = Field(default=None, ge=1)

class LLMProviderConfig(BaseModel):
    """LLM provider configuration."""
    api_key: Optional[str] = None
    base_url: str = Field(..., min_length=1)
    models: list[LLMModelConfig]
    rate_limit: RateLimitConfig
    timeout: int = Field(default=30, ge=1)
    
    @field_validator("base_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"Invalid URL format: {v}")
        return v

class LLMConfig(BaseModel):
    """LLM configuration model."""
    providers: dict[str, LLMProviderConfig]
    primary_provider: str
    fallback_chain: list[str]
    cross_validation: Optional[dict[str, Any]] = None
    analysis: Optional[dict[str, Any]] = None
    
    @field_validator("primary_provider")
    @classmethod
    def validate_primary_provider(cls, v: str, info) -> str:
        """Validate primary provider exists in providers."""
        if "providers" in info.data and v not in info.data["providers"]:
            raise ValueError(f"Primary provider '{v}' not found in providers")
        return v

class ExternalToolConfig(BaseModel):
    """External tool configuration."""
    name: str = Field(..., min_length=1)
    source_type: str = Field(..., pattern="^(github|local)$")
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    integration_method: str = Field(..., pattern="^(import|command_line)$")
    entry_point: Optional[str] = None
    command_template: Optional[str] = None
    risk_warning: str = Field(..., min_length=1)
    timeout: int = Field(default=30, ge=1)
    enabled: bool = Field(default=False)
    parameters: Optional[dict[str, Any]] = None

class ExternalToolsConfig(BaseModel):
    """External tools configuration model."""
    tools: list[ExternalToolConfig]
    security: Optional[dict[str, Any]] = None

def validate_yaml_file(file_path: Path, model_class: type[BaseModel]) -> Optional[BaseModel]:
    """
    Validate a YAML configuration file.
    
    Args:
        file_path: Path to YAML file
        model_class: Pydantic model class for validation
        
    Returns:
        Validated configuration model or None if validation fails
        
    Validates: Requirements 11.1, 11.2, 11.3
    """
    try:
        # Check file exists
        if not file_path.exists():
            logger.error(
                "configuration_file_not_found",
                file_path=str(file_path)
            )
            return None
        
        # Load YAML file
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                config_data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                logger.error(
                    "configuration_syntax_error",
                    file_path=str(file_path),
                    line_number=getattr(e, "problem_mark", {}).get("line", "unknown"),
                    error=str(e)
                )
                return None
        
        # Validate with Pydantic model
        try:
            config = model_class(**config_data)
            return config
        except ValidationError as e:
            logger.error(
                "configuration_validation_error",
                file_path=str(file_path),
                errors=e.errors()
            )
            return None
            
    except Exception as e:
        logger.error(
            "configuration_load_error",
            file_path=str(file_path),
            error=str(e)
        )
        return None

def validate_all_configs(config_dir: Path = Path("config")) -> bool:
    """
    Validate all configuration files.
    
    Args:
        config_dir: Directory containing configuration files
        
    Returns:
        True if all configurations are valid, False otherwise
        
    Validates: Requirements 11.6
    """
    all_valid = True
    
    # Validate fetch_sources.yaml
    fetch_config = validate_yaml_file(
        config_dir / "fetch_sources.yaml",
        FetchSourcesConfig
    )
    if fetch_config is None:
        all_valid = False
    
    # Validate llm_config.yaml
    llm_config = validate_yaml_file(
        config_dir / "llm_config.yaml",
        LLMConfig
    )
    if llm_config is None:
        all_valid = False
    
    # Validate external_tools.yaml
    tools_config = validate_yaml_file(
        config_dir / "external_tools.yaml",
        ExternalToolsConfig
    )
    if tools_config is None:
        all_valid = False
    
    if all_valid:
        logger.info("configuration_validation_successful")
        return True
    else:
        logger.error("configuration_validation_failed")
        return False

if __name__ == "__main__":
    """Run configuration validation from command line."""
    from system_core.config import setup_logging
    
    setup_logging(log_level="INFO")
    
    config_dir = Path("config")
    if len(sys.argv) > 1:
        config_dir = Path(sys.argv[1])
    
    if validate_all_configs(config_dir):
        sys.exit(0)
    else:
        sys.exit(1)
