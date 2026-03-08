"""
Global Configuration Manager
全局配置管理器

Provides a singleton instance of ConfigurationManager that manages all
configuration files with hot-reload support.

提供ConfigurationManager的单例实例，管理所有配置文件并支持热重载。
"""

import logging
from typing import Any, Optional
from pathlib import Path

from system_core.config.configuration_manager import ConfigurationManager
from system_core.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Global singleton instance / 全局单例实例
_global_config_manager: Optional[ConfigurationManager] = None

def get_global_config_manager(
    config_dir: str = "config",
    event_bus: Optional[Any] = None,
    auto_start: bool = True
) -> ConfigurationManager:
    """
    Get or create the global ConfigurationManager singleton instance.
    获取或创建全局ConfigurationManager单例实例。
    
    This ensures all modules use the same configuration manager instance,
    enabling true global configuration with hot-reload support.
    
    这确保所有模块使用相同的配置管理器实例，实现真正的全局配置和热重载支持。
    
    Args:
        config_dir: Configuration directory path / 配置目录路径
        event_bus: Event bus instance for publishing events / 事件总线实例
        auto_start: Automatically start file monitoring / 自动启动文件监控
        
    Returns:
        ConfigurationManager singleton instance / ConfigurationManager单例实例
    """
    global _global_config_manager
    
    if _global_config_manager is None:
        logger.info("Initializing global configuration manager / 初始化全局配置管理器")
        
        _global_config_manager = ConfigurationManager(
            config_dir=config_dir,
            event_bus=event_bus
        )
        
        # Add all configuration files to watch list / 添加所有配置文件到监控列表
        config_files = [
            'fetch_sources.yaml',      # 数据获取源配置
            'llm_config.yaml',          # LLM模型配置
            'push_config.yaml',         # 推送通知配置
            'prompt_templates.yaml',    # 提示模板配置
            'external_tools.yaml',      # 外部工具配置
            'keywords.yaml',            # 关键词配置
            'assets.yaml',              # 资产配置
            'accounts.yaml',            # 账户配置
            'ea_config.yaml',           # EA配置
            'factor_config.yaml',       # 因子配置
            'alerting_config.yaml',     # 警报配置
            'audit_config.yaml',        # 审计配置
            'backup_config.yaml',       # 备份配置
            'retention_policy.yaml',    # 保留策略配置
            'security_config.yaml',     # 安全配置
            'vector_db.yaml',           # 向量数据库配置
            'event_bus.yaml',           # 事件总线配置
            'profiles.yaml',            # 配置文件
        ]
        
        for config_file in config_files:
            _global_config_manager.add_watched_file(config_file)
        
        if auto_start:
            try:
                _global_config_manager.start()
                logger.info(
                    f"Global configuration manager started, monitoring {len(config_files)} files / "
                    f"全局配置管理器已启动，监控 {len(config_files)} 个文件"
                )
            except Exception as e:
                logger.error(f"Failed to start configuration manager: {e}")
    
    return _global_config_manager

def get_config(filename: str) -> Optional[dict[str, Any]]:
    """
    Get configuration from global manager.
    从全局管理器获取配置。
    
    Args:
        filename: Configuration file name / 配置文件名
        
    Returns:
        Configuration dictionary or None / 配置字典或None
    """
    manager = get_global_config_manager()
    return manager.get_config(filename)

def reload_config(filename: str) -> bool:
    """
    Reload specific configuration file.
    重新加载特定配置文件。
    
    Args:
        filename: Configuration file name / 配置文件名
        
    Returns:
        True if reload successful / 重载成功返回True
    """
    import asyncio
    
    manager = get_global_config_manager()
    
    # Run async reload in sync context / 在同步上下文中运行异步重载
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(manager.reload_config(filename))

def get_llm_config() -> Optional[dict[str, Any]]:
    """Get LLM configuration / 获取LLM配置"""
    return get_config('llm_config.yaml')

def get_factor_config() -> Optional[dict[str, Any]]:
    """Get factor configuration / 获取因子配置"""
    return get_config('factor_config.yaml')

def get_fetch_config() -> Optional[dict[str, Any]]:
    """Get fetch sources configuration / 获取数据获取源配置"""
    return get_config('fetch_sources.yaml')

def get_push_config() -> Optional[dict[str, Any]]:
    """Get push notification configuration / 获取推送通知配置"""
    return get_config('push_config.yaml')

def get_ea_config() -> Optional[dict[str, Any]]:
    """Get EA configuration / 获取EA配置"""
    return get_config('ea_config.yaml')

def get_accounts_config() -> Optional[dict[str, Any]]:
    """Get accounts configuration / 获取账户配置"""
    return get_config('accounts.yaml')

def get_keywords_config() -> Optional[dict[str, Any]]:
    """Get keywords configuration / 获取关键词配置"""
    return get_config('keywords.yaml')

def get_assets_config() -> Optional[dict[str, Any]]:
    """Get assets configuration / 获取资产配置"""
    return get_config('assets.yaml')

def register_config_callback(filename: str, callback):
    """
    Register callback for configuration changes.
    注册配置变更回调。
    
    Args:
        filename: Configuration file name / 配置文件名
        callback: Callback function (sync or async) / 回调函数（同步或异步）
    """
    manager = get_global_config_manager()
    manager.register_callback(filename, callback)

def get_config_statistics() -> dict[str, Any]:
    """
    Get configuration manager statistics.
    获取配置管理器统计信息。
    
    Returns:
        Statistics dictionary / 统计信息字典
    """
    manager = get_global_config_manager()
    return manager.get_statistics()

# Convenience function for getting all configs / 便捷函数：获取所有配置
def get_all_configs() -> dict[str, dict[str, Any]]:
    """
    Get all loaded configurations.
    获取所有已加载的配置。
    
    Returns:
        Dictionary mapping filename to configuration / 文件名到配置的字典映射
    """
    manager = get_global_config_manager()
    
    config_files = [
        'llm_config.yaml',
        'factor_config.yaml',
        'fetch_sources.yaml',
        'push_config.yaml',
        'ea_config.yaml',
        'accounts.yaml',
        'keywords.yaml',
        'assets.yaml',
    ]
    
    configs = {}
    for filename in config_files:
        config = manager.get_config(filename)
        if config is not None:
            configs[filename] = config
    
    return configs

__all__ = [
    'get_global_config_manager',
    'get_config',
    'reload_config',
    'get_llm_config',
    'get_factor_config',
    'get_fetch_config',
    'get_push_config',
    'get_ea_config',
    'get_accounts_config',
    'get_keywords_config',
    'get_assets_config',
    'register_config_callback',
    'get_config_statistics',
    'get_all_configs',
]
