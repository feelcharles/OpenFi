"""
LLM Model Data Structures and Configuration Loader

This module contains the core data models and configuration loading logic
for the LLM model switching feature.

Validates: Requirements 1.1, 1.2, 1.3, 1.4
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)

@dataclass
class ModelConfig:
    """
    模型配置数据类
    
    Validates: Requirement 1.1, 1.2, 1.3
    """
    # 基本信息
    id: int  # 模型编号（从1开始）
    name: str  # API 名称
    display_name: str  # 显示名称
    provider: str  # 提供商（openai, anthropic, local）
    type: str  # 模型类型（fast, pro）
    
    # 参数配置
    max_tokens: int  # 最大 token 数
    temperature: float = 0.7  # 温度参数
    context_window: Optional[int] = None  # 上下文窗口大小
    
    # 成本信息
    cost_per_1k_tokens: float = 0.0  # 每1K tokens的成本
    
    # API 配置
    api_key: Optional[str] = None  # API 密钥
    base_url: Optional[str] = None  # API 基础 URL
    
    def __post_init__(self):
        """验证必填字段 - Validates: Requirement 1.2, 1.3"""
        if not self.name:
            raise ValueError("Model name is required")
        if not self.display_name:
            raise ValueError("Model display_name is required")
        if self.type not in ["fast", "pro"]:
            raise ValueError(f"Invalid model type: {self.type}. Must be 'fast' or 'pro'")

@dataclass
class AutoSelectionConfig:
    """
    自动选择配置
    
    Validates: Requirements 5.1, 5.2, 5.3, 6.1-6.5, 7.1-7.5, 8.1-8.5
    """
    enabled: bool = True
    strategy: str = "adaptive"  # adaptive, cost_optimized, performance_optimized
    
    # 自适应策略配置
    simple_tasks: list[str] = field(default_factory=list)
    complex_tasks: list[str] = field(default_factory=list)
    length_threshold: int = 1000
    
    # 成本优化配置
    prefer_fast: bool = True
    pro_threshold: float = 0.8
    
    # 性能优化配置
    prefer_pro: bool = True
    fast_threshold: float = 0.3

@dataclass
class UsageStats:
    """
    使用统计数据
    
    Validates: Requirements 10.1, 10.2, 10.3, 10.4
    """
    model_name: str
    request_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    last_used: Optional[str] = None  # ISO format datetime string

class ConfigurationError(Exception):
    """
    配置错误异常
    
    Validates: Requirement 1.4
    """
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.details = details or {}
        self.message = message

class ConfigurationLoader:
    """
    配置文件加载器
    
    Validates: Requirements 1.1, 1.2, 1.3, 1.4
    """
    
    @staticmethod
    def load(config_path: str) -> dict[str, Any]:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            Dict: 配置字典
            
        Raises:
            ConfigurationError: 文件不存在或格式错误
            
        Validates: Requirement 1.1, 1.4
        """
        try:
            path = Path(config_path)
            if not path.exists():
                raise ConfigurationError(
                    f"Configuration file not found: {config_path}",
                    {"path": config_path}
                )
            
            with open(path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if not config:
                raise ConfigurationError(
                    f"Configuration file is empty: {config_path}",
                    {"path": config_path}
                )
            
            logger.info(f"Successfully loaded configuration from {config_path}")
            return config
            
        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"Invalid YAML format in configuration file: {config_path}",
                {"path": config_path, "yaml_error": str(e)}
            )
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(
                f"Failed to load configuration: {str(e)}",
                {"path": config_path, "error": str(e)}
            )
    
    @staticmethod
    def validate_model(model_config: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        验证单个模型配置
        
        Args:
            model_config: 模型配置字典
            
        Returns:
            (是否有效, 错误消息)
            
        Validates: Requirement 1.2, 1.3
        """
        # 检查必填字段
        required_fields = ['name', 'display_name', 'type']
        for field in required_fields:
            if field not in model_config or not model_config[field]:
                return False, f"Missing required field: {field}"
        
        # 验证类型字段
        model_type = model_config.get('type')
        if model_type not in ['fast', 'pro']:
            return False, f"Invalid model type: {model_type}. Must be 'fast' or 'pro'"
        
        return True, None
    
    @staticmethod
    def parse_models(config: dict[str, Any]) -> list[ModelConfig]:
        """
        解析配置文件中的所有模型
        
        Args:
            config: 配置字典
            
        Returns:
            list[ModelConfig]: 解析后的模型列表
            
        Validates: Requirements 1.1, 1.2, 1.3, 1.5
        """
        models = []
        model_id = 1  # 从1开始编号
        
        providers = config.get('providers', {})
        if not providers:
            logger.warning("No providers found in configuration")
            return models
        
        for provider_name, provider_config in providers.items():
            provider_models = provider_config.get('models', [])
            
            for model_data in provider_models:
                # 验证模型配置
                is_valid, error_msg = ConfigurationLoader.validate_model(model_data)
                
                if not is_valid:
                    logger.warning(
                        f"Skipping invalid model in provider {provider_name}: {error_msg}",
                        extra={"provider": provider_name, "model_data": model_data}
                    )
                    continue
                
                try:
                    # 创建 ModelConfig 实例
                    model = ModelConfig(
                        id=model_id,
                        name=model_data['name'],
                        display_name=model_data.get('display_name', model_data['name']),
                        provider=provider_name,
                        type=model_data['type'],
                        max_tokens=model_data.get('max_tokens', 4096),
                        temperature=model_data.get('temperature', 0.7),
                        context_window=model_data.get('context_window'),
                        cost_per_1k_tokens=model_data.get('cost_per_1k_tokens', 0.0),
                        api_key=provider_config.get('api_key'),
                        base_url=provider_config.get('base_url')
                    )
                    
                    models.append(model)
                    model_id += 1
                    
                    logger.debug(
                        f"Loaded model: {model.display_name} (ID: {model.id}, Type: {model.type})"
                    )
                    
                except Exception as e:
                    logger.warning(
                        f"Failed to create ModelConfig for {model_data.get('name', 'unknown')}: {e}",
                        extra={"provider": provider_name, "error": str(e)}
                    )
                    continue
        
        logger.info(f"Successfully parsed {len(models)} models from configuration")
        return models
