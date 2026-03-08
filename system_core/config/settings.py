"""
Application settings management using Pydantic.

Validates: Requirements 11.1, 11.2, 11.3, 11.4
"""

from functools import lru_cache
from typing import Optional
from pydantic import Field, field_validator, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings with validation."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_name: str = Field(default="OpenFi")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # Database
    db_user: str = Field(default="openfi", description="Database user")
    db_password: str = Field(default="openfi_password", description="Database password")
    db_host: str = Field(default="localhost", description="Database host")
    db_port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    db_name: str = Field(default="openfi", description="Database name")
    database_pool_min: int = Field(default=5, ge=1)
    database_pool_max: int = Field(default=20, ge=5)
    
    @property
    def database_url(self) -> str:
        """Construct database URL from components."""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    redis_password: Optional[str] = Field(default=None)
    
    # Time Series Database
    timeseries_url: Optional[str] = Field(default=None)
    
    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production-32chars", min_length=32, description="Secret key for JWT signing")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_hours: int = Field(default=24, ge=1)
    encryption_key: str = Field(default="dev-encryption-key-change-prod-32c", min_length=32, description="AES-256 encryption key")
    
    # External Data Sources
    forexfactory_api_key: Optional[str] = Field(default=None)
    alphavantage_api_key: Optional[str] = Field(default=None)
    newsapi_key: Optional[str] = Field(default=None)
    twitter_api_key: Optional[str] = Field(default=None)
    twitter_api_secret: Optional[str] = Field(default=None)
    
    # LLM Providers
    openai_api_key: Optional[str] = Field(default=None)
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    anthropic_api_key: Optional[str] = Field(default=None)
    anthropic_base_url: str = Field(default="https://api.anthropic.com")
    local_llm_url: Optional[str] = Field(default=None)
    
    # Vector Database
    vector_db_provider: str = Field(default="pinecone")
    pinecone_api_key: Optional[str] = Field(default=None)
    pinecone_environment: Optional[str] = Field(default=None)
    pinecone_index_name: Optional[str] = Field(default="OpenFi-vectors")
    
    # Push Channels
    telegram_bot_token: Optional[str] = Field(default=None)
    discord_bot_token: Optional[str] = Field(default=None)
    feishu_app_id: Optional[str] = Field(default=None)
    feishu_app_secret: Optional[str] = Field(default=None)
    wechat_work_corp_id: Optional[str] = Field(default=None)
    wechat_work_agent_id: Optional[str] = Field(default=None)
    wechat_work_secret: Optional[str] = Field(default=None)
    smtp_host: Optional[str] = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_user: Optional[str] = Field(default=None)
    smtp_password: Optional[str] = Field(default=None)
    
    # Broker Adapters
    mt4_server: Optional[str] = Field(default=None)
    mt4_login: Optional[str] = Field(default=None)
    mt4_password: Optional[str] = Field(default=None)
    
    # Web Backend
    web_backend_host: str = Field(default="0.0.0.0", description="Web backend host")
    web_backend_port: int = Field(default=8686, ge=1024, le=65535, description="Web backend port")
    
    # Monitoring
    prometheus_port: int = Field(default=9090, ge=1024, le=65535)
    alert_webhook_url: Optional[str] = Field(default=None)
    
    # Logging
    log_file_path: str = Field(default="logs/OpenFi.log")
    log_max_bytes: int = Field(default=104857600, description="100MB in bytes")
    log_backup_count: int = Field(default=10)
    log_retention_days: int = Field(default=30, ge=1)
    
    # Configuration
    config_dir: str = Field(default="config", description="Configuration files directory")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v_upper
    
    @field_validator("vector_db_provider")
    @classmethod
    def validate_vector_db_provider(cls, v: str) -> str:
        """Validate vector database provider."""
        valid_providers = ["pinecone", "weaviate", "qdrant"]
        v_lower = v.lower()
        if v_lower not in valid_providers:
            raise ValueError(f"vector_db_provider must be one of {valid_providers}")
        return v_lower
    
    @field_validator("database_pool_max")
    @classmethod
    def validate_pool_max(cls, v: int, info) -> int:
        """Ensure max pool size is greater than min pool size."""
        if "database_pool_min" in info.data and v < info.data["database_pool_min"]:
            raise ValueError("database_pool_max must be >= database_pool_min")
        return v

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Settings: Application settings
        
    Raises:
        ValidationError: If required settings are missing or invalid
    """
    return Settings()
