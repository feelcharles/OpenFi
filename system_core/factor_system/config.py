"""
Factor System Configuration Manager

Handles loading, validation, and management of factor system configuration from YAML files.
Supports environment variable overrides for sensitive information.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, validator

from system_core.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# ============================================
# Pydantic Configuration Models
# ============================================

class FactorLibraryConfig(BaseModel):
    """Factor library configuration"""
    path: str = Field(default="factors/", description="Factor library directory path")
    auto_reload: bool = Field(default=True, description="Enable automatic factor code reload")
    reload_interval: int = Field(default=60, ge=1, description="Reload interval in seconds")
    max_factor_size: int = Field(default=1048576, ge=1024, description="Maximum factor file size in bytes")
    allowed_extensions: list[str] = Field(default=[".py"], description="Allowed file extensions")

class DataSourceConfig(BaseModel):
    """Data source configuration"""
    adapter: str = Field(..., description="Adapter class path")
    api_endpoint: Optional[str] = Field(None, description="API endpoint URL")
    api_key: Optional[str] = Field(None, description="API key")
    cache_ttl: int = Field(default=3600, ge=0, description="Cache TTL in seconds")
    timeout: int = Field(default=30, ge=1, le=300, description="Request timeout in seconds")
    retry_attempts: int = Field(default=3, ge=0, le=10, description="Number of retry attempts")
    retry_delay: int = Field(default=1, ge=0, description="Delay between retries in seconds")

class EngineConfig(BaseModel):
    """Factor calculation engine configuration"""
    max_workers: int = Field(default=4, ge=1, le=32, description="Maximum worker processes")
    calculation_timeout: int = Field(default=5, ge=1, description="Single factor calculation timeout in seconds")
    batch_calculation_timeout: int = Field(default=60, ge=1, description="Batch calculation timeout in seconds")
    enable_parallel: bool = Field(default=True, description="Enable parallel computation")
    memory_limit: int = Field(default=4294967296, ge=1073741824, description="Memory limit in bytes")

class BacktestConfig(BaseModel):
    """Backtest engine configuration"""
    default_initial_capital: float = Field(default=100000, gt=0, description="Default initial capital")
    default_commission: float = Field(default=0.001, ge=0, le=0.1, description="Default commission rate")
    default_slippage: float = Field(default=0.0005, ge=0, le=0.1, description="Default slippage rate")
    default_leverage: float = Field(default=1.0, ge=1, le=100, description="Default leverage")
    max_backtest_years: int = Field(default=10, ge=1, le=50, description="Maximum backtest years")
    timeout: int = Field(default=60, ge=1, description="Backtest timeout in seconds")

class ScreeningConfig(BaseModel):
    """Factor screening configuration"""
    max_symbols: int = Field(default=10000, ge=1, description="Maximum symbols to screen")
    timeout: int = Field(default=3, ge=1, description="Screening timeout in seconds")
    default_top_n: int = Field(default=10, ge=1, description="Default top N results")
    industry_classification: str = Field(default="GICS", description="Industry classification system")

class OptimizationConfig(BaseModel):
    """Factor optimization configuration"""
    methods: list[str] = Field(default=["equal_weight", "ic_weighted", "max_sharpe"], description="Available optimization methods")
    default_method: str = Field(default="max_sharpe", description="Default optimization method")
    lookback_period: int = Field(default=252, ge=1, description="Lookback period in days")
    rebalance_frequency: int = Field(default=20, ge=1, description="Rebalance frequency in days")
    timeout: int = Field(default=30, ge=1, description="Optimization timeout in seconds")
    
    @validator('default_method')
    def validate_default_method(cls, v, values):
        """Validate default method is in available methods"""
        if 'methods' in values and v not in values['methods']:
            raise ValueError(f"default_method must be one of {values['methods']}")
        return v

class PerformanceConfig(BaseModel):
    """Performance thresholds configuration"""
    max_factor_calculation_time: int = Field(default=5, ge=1, description="Max factor calculation time in seconds")
    max_batch_calculation_time: int = Field(default=60, ge=1, description="Max batch calculation time in seconds")
    max_screening_time: int = Field(default=3, ge=1, description="Max screening time in seconds")
    max_optimization_time: int = Field(default=30, ge=1, description="Max optimization time in seconds")

class CacheConfig(BaseModel):
    """Cache configuration"""
    enabled: bool = Field(default=True, description="Enable caching")
    backend: str = Field(default="redis", description="Cache backend")
    host: str = Field(default="localhost", description="Cache host")
    port: int = Field(default=6379, ge=1, le=65535, description="Cache port")
    password: Optional[str] = Field(None, description="Cache password")
    db: int = Field(default=2, ge=0, le=15, description="Redis database number")
    ttl: int = Field(default=3600, ge=0, description="Default TTL in seconds")
    max_size: int = Field(default=10000, ge=1, description="Maximum cache size")

class LLMIntegrationConfig(BaseModel):
    """LLM integration configuration"""
    enabled: bool = Field(default=True, description="Enable LLM integration")
    analysis_timeout: int = Field(default=20, ge=1, description="Analysis timeout in seconds")
    max_tokens: int = Field(default=2000, ge=100, description="Maximum tokens per request")
    temperature: float = Field(default=0.7, ge=0, le=2, description="LLM temperature")

class PushIntegrationConfig(BaseModel):
    """Push service integration configuration"""
    enabled: bool = Field(default=True, description="Enable factor filtering in push service")
    pre_push_backtest_enabled: bool = Field(default=True, description="Enable pre-push backtest")
    lookback_days: int = Field(default=60, ge=1, description="Backtest lookback days")
    min_sharpe_ratio: float = Field(default=1.0, ge=0, description="Minimum Sharpe ratio threshold")
    max_drawdown: float = Field(default=0.2, ge=0, le=1, description="Maximum drawdown threshold")
    min_win_rate: float = Field(default=0.5, ge=0, le=1, description="Minimum win rate threshold")
    timeout: int = Field(default=10, ge=1, description="Pre-push backtest timeout in seconds")

class FactorSystemConfig(BaseModel):
    """Complete factor system configuration"""
    factor_library: FactorLibraryConfig = Field(default_factory=FactorLibraryConfig)
    data_sources: dict[str, DataSourceConfig] = Field(default_factory=dict)
    engine: EngineConfig = Field(default_factory=EngineConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    screening: ScreeningConfig = Field(default_factory=ScreeningConfig)
    optimization: OptimizationConfig = Field(default_factory=OptimizationConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    llm: LLMIntegrationConfig = Field(default_factory=LLMIntegrationConfig)
    push: PushIntegrationConfig = Field(default_factory=PushIntegrationConfig)

# ============================================
# Configuration Manager
# ============================================

class FactorConfigManager:
    """
    Factor system configuration manager.
    
    Loads and validates factor system configuration from YAML files,
    with support for environment variable overrides.
    """
    
    def __init__(self, config_path: str = "config/factor_config.yaml"):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = Path(config_path)
        self._config: Optional[FactorSystemConfig] = None
    
    def load_config(self) -> FactorSystemConfig:
        """
        Load and validate configuration from file.
        
        Returns:
            Validated configuration object
            
        Raises:
            ConfigurationError: If configuration is invalid or file not found
        """
        try:
            # Check if file exists
            if not self.config_path.exists():
                logger.warning(f"Configuration file not found: {self.config_path}, using defaults")
                self._config = FactorSystemConfig()
                return self._config
            
            # Load YAML file
            with open(self.config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f)
            
            if not raw_config:
                logger.warning("Empty configuration file, using defaults")
                self._config = FactorSystemConfig()
                return self._config
            
            # Extract factor_system section
            factor_config = raw_config.get('factor_system', {})
            
            # Apply environment variable overrides
            factor_config = self._apply_env_overrides(factor_config)
            
            # Validate and create config object
            self._config = FactorSystemConfig(**factor_config)
            
            logger.info(f"Successfully loaded factor system configuration from {self.config_path}")
            return self._config
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML format in {self.config_path}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    def _apply_env_overrides(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Apply environment variable overrides to configuration.
        
        Environment variables follow the pattern: FACTOR_<SECTION>_<KEY>
        Example: FACTOR_CACHE_HOST, FACTOR_ENGINE_MAX_WORKERS
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Configuration with environment overrides applied
        """
        # Data source API keys and endpoints
        if 'data_sources' in config:
            for source_name, source_config in config['data_sources'].items():
                # Override API endpoint
                env_key = f"FACTOR_DATA_{source_name.upper()}_API_ENDPOINT"
                if env_key in os.environ:
                    source_config['api_endpoint'] = os.environ[env_key]
                    logger.info(f"Overriding {source_name} API endpoint from environment")
                
                # Override API key
                env_key = f"FACTOR_DATA_{source_name.upper()}_API_KEY"
                if env_key in os.environ:
                    source_config['api_key'] = os.environ[env_key]
                    logger.info(f"Overriding {source_name} API key from environment")
        
        # Cache configuration
        if 'cache' in config:
            if 'FACTOR_CACHE_HOST' in os.environ:
                config['cache']['host'] = os.environ['FACTOR_CACHE_HOST']
                logger.info("Overriding cache host from environment")
            
            if 'FACTOR_CACHE_PORT' in os.environ:
                config['cache']['port'] = int(os.environ['FACTOR_CACHE_PORT'])
                logger.info("Overriding cache port from environment")
            
            if 'FACTOR_CACHE_PASSWORD' in os.environ:
                config['cache']['password'] = os.environ['FACTOR_CACHE_PASSWORD']
                logger.info("Overriding cache password from environment")
        
        # Engine configuration
        if 'engine' in config:
            if 'FACTOR_ENGINE_MAX_WORKERS' in os.environ:
                config['engine']['max_workers'] = int(os.environ['FACTOR_ENGINE_MAX_WORKERS'])
                logger.info("Overriding engine max_workers from environment")
        
        return config
    
    def get_config(self) -> FactorSystemConfig:
        """
        Get current configuration.
        
        Returns:
            Current configuration object
            
        Raises:
            ConfigurationError: If configuration not loaded
        """
        if self._config is None:
            raise ConfigurationError("Configuration not loaded. Call load_config() first.")
        return self._config
    
    def reload_config(self) -> FactorSystemConfig:
        """
        Reload configuration from file.
        
        Returns:
            Reloaded configuration object
        """
        logger.info("Reloading factor system configuration")
        return self.load_config()
    
    def validate_config(self, config_dict: dict[str, Any]) -> bool:
        """
        Validate configuration dictionary without loading.
        
        Args:
            config_dict: Configuration dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            FactorSystemConfig(**config_dict)
            return True
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

# ============================================
# Global Configuration Instance
# ============================================

_config_manager: Optional[FactorConfigManager] = None

def get_factor_config_manager() -> FactorConfigManager:
    """
    Get global factor configuration manager instance.
    
    Returns:
        Global configuration manager
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = FactorConfigManager()
    return _config_manager

def load_factor_config(config_path: str = "config/factor_config.yaml") -> FactorSystemConfig:
    """
    Load factor system configuration.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Loaded configuration
    """
    manager = FactorConfigManager(config_path)
    return manager.load_config()
