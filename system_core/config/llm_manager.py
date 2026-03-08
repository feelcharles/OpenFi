"""
LLM Manager - 大模型管理器

负责管理多个LLM模型的切换、自动选择和使用统计

Validates: Requirements 1.1-1.5, 3.1-3.5, 4.1-4.5, 5.1-5.5, 9.1-9.5, 10.1-10.5, 11.1-11.5, 12.1-12.5
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from system_core.config.llm_models import (
    ModelConfig,
    AutoSelectionConfig,
    ConfigurationLoader,
    ConfigurationError
)
from system_core.config.llm_selector import ModelSelector
from system_core.config.llm_statistics import get_usage_statistics
from system_core.config.file_watcher import FileWatcher
from system_core.config.global_config import get_llm_config, register_config_callback

logger = logging.getLogger(__name__)

class LLMManager:
    """
    LLM管理器
    
    Validates: Requirements 1.1-1.5, 3.1-3.5, 4.1-4.5, 5.1-5.5, 10.1-10.5, 11.1-11.5, 12.1-12.5
    """
    
    def __init__(self, enable_auto_reload: bool = True):
        """
        初始化管理器，加载配置
        
        Args:
            enable_auto_reload: 是否启用配置文件自动重载
        
        Validates: Requirement 1.1, 11.5, 12.1
        """
        # Use global configuration manager
        self.config = get_llm_config()
        self.models: list[ModelConfig] = []
        self.current_model: Optional[ModelConfig] = None
        self.auto_mode = False
        self.model_selector: Optional[ModelSelector] = None
        self.statistics = get_usage_statistics()
        self.file_watcher: Optional[FileWatcher] = None
        
        self._load_models()
        self._set_default_model()
        self._initialize_selector()
        
        # 启用配置文件监控（如果需要）
        if enable_auto_reload:
            self._start_file_watcher()
        
        logger.info(
            f"LLM Manager initialized: {len(self.models)} models loaded, "
            f"default model: {self.current_model.display_name if self.current_model else 'None'}, "
            f"auto-reload: {enable_auto_reload}"
        )
    
    def _load_config(self) -> dict:
        """
        加载配置文件
        
        Validates: Requirement 1.1, 1.4
        """
        try:
            return ConfigurationLoader.load(str(self.config_path))
        except ConfigurationError as e:
            logger.error(f"Configuration error: {e.message}", extra=e.details)
            raise
        except Exception as e:
            logger.error(f"Failed to load LLM config: {e}")
            return {}
    
    def _load_models(self):
        """
        加载所有可用模型
        
        Validates: Requirements 1.1, 1.2, 1.3, 1.5
        """
        try:
            self.models = ConfigurationLoader.parse_models(self.config)
            logger.info(f"Loaded {len(self.models)} LLM models")
        except Exception as e:
            logger.error(f"Failed to parse models from configuration: {e}")
            self.models = []
    
    def _set_default_model(self):
        """
        设置默认模型
        
        Validates: Requirement 1.1, 11.5
        """
        default_config = self.config.get('default_model', {})
        provider = default_config.get('provider', 'openai')
        model_name = default_config.get('model', 'gpt-3.5-turbo')
        
        for model in self.models:
            if model.provider == provider and model.name == model_name:
                self.current_model = model
                logger.info(f"Set default model: {model.display_name}")
                return
        
        # 如果找不到默认模型，使用第一个可用模型
        if self.models:
            self.current_model = self.models[0]
            logger.warning(f"Default model not found, using: {self.current_model.display_name}")
    
    def _initialize_selector(self):
        """
        初始化模型选择器
        
        Validates: Requirement 5.4
        """
        auto_selection_config = self.config.get('auto_selection', {})
        if auto_selection_config.get('enabled', True):
            self.model_selector = ModelSelector(auto_selection_config)
            logger.info("Model selector initialized")
    
    def _start_file_watcher(self):
        """
        启动配置文件监控
        
        Validates: Requirements 12.1, 12.2
        """
        try:
            # Register callback with global config manager
            register_config_callback('llm_config.yaml', self._on_config_changed)
            logger.info("Registered callback with global configuration manager")
        except Exception as e:
            logger.error(f"Failed to register config callback: {e}")
    
    def _on_config_changed(self, config_name: str, new_config: dict):
        """
        配置文件变化时的回调
        
        Validates: Requirements 12.2, 12.3, 12.4, 12.5
        """
        logger.info(f"Configuration file {config_name} changed, reloading...")
        self.config = new_config
        self._load_models()
        self._initialize_selector()
        logger.info("LLM configuration reloaded successfully")
        if success:
            logger.info(f"Auto-reload successful: {message}")
        else:
            logger.error(f"Auto-reload failed: {message}")
    
    def stop_file_watcher(self):
        """
        停止配置文件监控
        
        Validates: Requirement 12.1
        """
        if self.file_watcher:
            self.file_watcher.stop()
            logger.info("Configuration file watcher stopped")
    
    def get_all_models(self) -> list[ModelConfig]:
        """获取所有模型 - Validates: Requirement 2.1"""
        return self.models
    
    def get_fast_models(self) -> list[ModelConfig]:
        """获取所有fast模型 - Validates: Requirement 4.1"""
        return [m for m in self.models if m.type == 'fast']
    
    def get_pro_models(self) -> list[ModelConfig]:
        """获取所有pro模型 - Validates: Requirement 4.2"""
        return [m for m in self.models if m.type == 'pro']
    
    def get_model_by_index(self, index: int) -> Optional[ModelConfig]:
        """
        根据编号获取模型（从1开始）
        
        Validates: Requirement 1.5, 3.1
        """
        if 1 <= index <= len(self.models):
            return self.models[index - 1]
        return None
    
    def switch_model(self, index: int) -> tuple[bool, str, Optional[ModelConfig]]:
        """
        切换模型
        
        Returns:
            (success, message, old_model)
            
        Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
        """
        old_model = self.current_model
        new_model = self.get_model_by_index(index)
        
        if not new_model:
            error_msg = f"模型编号 {index} 不存在，有效范围是 1-{len(self.models)}"
            logger.warning(error_msg)
            return False, error_msg, old_model
        
        self.current_model = new_model
        self.auto_mode = False
        
        logger.info(
            f"Switched model from {old_model.display_name if old_model else 'None'} "
            f"to {new_model.display_name}"
        )
        return True, f"已切换到 {new_model.display_name}", old_model
    
    def switch_to_fast(self) -> tuple[bool, str, Optional[ModelConfig]]:
        """
        切换到默认fast模型
        
        Validates: Requirements 4.1, 4.3, 4.4, 4.5
        """
        old_model = self.current_model
        fast_models = self.get_fast_models()
        
        if not fast_models:
            error_msg = "没有可用的 fast 模型"
            logger.warning(error_msg)
            return False, error_msg, old_model
        
        # 使用第一个fast模型
        self.current_model = fast_models[0]
        self.auto_mode = False
        
        logger.info(f"Switched to fast model: {self.current_model.display_name}")
        return True, f"已切换到 fast 模型: {self.current_model.display_name}", old_model
    
    def switch_to_pro(self) -> tuple[bool, str, Optional[ModelConfig]]:
        """
        切换到默认pro模型
        
        Validates: Requirements 4.2, 4.3, 4.4, 4.5
        """
        old_model = self.current_model
        pro_models = self.get_pro_models()
        
        if not pro_models:
            error_msg = "没有可用的 pro 模型"
            logger.warning(error_msg)
            return False, error_msg, old_model
        
        # 使用第一个pro模型
        self.current_model = pro_models[0]
        self.auto_mode = False
        
        logger.info(f"Switched to pro model: {self.current_model.display_name}")
        return True, f"已切换到 pro 模型: {self.current_model.display_name}", old_model
    
    def enable_auto_mode(self) -> tuple[bool, str]:
        """
        启用自动模式
        
        Validates: Requirements 5.1, 5.2, 5.3
        """
        self.auto_mode = True
        auto_config = self.config.get('auto_selection', {})
        strategy = auto_config.get('strategy', 'adaptive')
        
        logger.info(f"Enabled auto mode with strategy: {strategy}")
        return True, f"已启用自动模式 (策略: {strategy})"
    
    def disable_auto_mode(self):
        """
        禁用自动模式
        
        Validates: Requirement 5.5
        """
        self.auto_mode = False
        logger.info("Disabled auto mode")
    
    def is_auto_mode_enabled(self) -> bool:
        """
        检查自动模式是否启用
        
        Validates: Requirement 5.4
        """
        return self.auto_mode
    
    def select_model_for_task(self, task_type: str = None, input_length: int = 0) -> ModelConfig:
        """
        根据任务类型和输入长度自动选择模型
        
        Args:
            task_type: 任务类型 (translation, analysis, summarization, etc.)
            input_length: 输入文本长度
        
        Returns:
            选择的模型
            
        Validates: Requirements 5.4, 6.1-6.5, 7.1-7.5, 8.1-8.5, 11.4
        """
        if not self.auto_mode:
            return self.current_model
        
        if not self.model_selector:
            logger.warning("Model selector not initialized, using current model")
            return self.current_model
        
        try:
            selected_model = self.model_selector.select(
                self.models,
                task_type,
                input_length
            )
            
            logger.debug(
                f"Auto-selected model: {selected_model.display_name} "
                f"(task: {task_type}, length: {input_length})"
            )
            
            return selected_model
            
        except Exception as e:
            logger.error(f"Failed to auto-select model: {e}, using current model")
            return self.current_model
    
    def get_statistics(self) -> dict:
        """
        获取使用统计信息
        
        Validates: Requirements 10.1, 10.3
        """
        return {
            'daily': self.statistics.get_daily_stats(),
            'monthly': self.statistics.get_monthly_stats(),
            'current_model': self.current_model.display_name if self.current_model else None
        }
    
    def reload_config(self) -> tuple[bool, str]:
        """
        重新加载配置文件
        
        Returns:
            (成功标志, 消息)
            
        Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5
        """
        try:
            logger.info("Reloading configuration...")
            
            # 保存当前模型信息
            old_model_id = self.current_model.id if self.current_model else None
            old_model_name = self.current_model.name if self.current_model else None
            old_model_provider = self.current_model.provider if self.current_model else None
            
            # 重新加载配置
            self.config = self._load_config()
            self._load_models()
            self._initialize_selector()
            
            # 尝试恢复当前模型
            model_found = False
            if old_model_name and old_model_provider:
                for model in self.models:
                    if model.name == old_model_name and model.provider == old_model_provider:
                        self.current_model = model
                        model_found = True
                        logger.info(f"Restored current model: {model.display_name}")
                        break
            
            # 如果当前模型不存在，切换到默认模型
            if not model_found:
                self._set_default_model()
                logger.warning(
                    f"Previous model not found in new configuration, "
                    f"switched to default: {self.current_model.display_name if self.current_model else 'None'}"
                )
            
            logger.info(
                f"Configuration reloaded successfully: {len(self.models)} models loaded"
            )
            
            return True, f"配置已重新加载，当前有 {len(self.models)} 个模型可用"
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}", exc_info=True)
            return False, f"配置重载失败: {str(e)}"
    
    def get_model_list_text(self) -> str:
        """
        获取模型列表的文本表示（用于bot命令响应）
        
        Returns:
            格式化的模型列表文本
            
        Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
        """
        fast_models = self.get_fast_models()
        pro_models = self.get_pro_models()
        
        text = "🧠 大模型列表\n\n"
        text += f"📌 当前使用: {self.current_model.display_name} ({self.current_model.type})\n"
        
        if self.auto_mode:
            text += "🤖 自动模式: 已启用\n"
        
        text += "\n⚡ Fast 模型 (快速响应):\n"
        for i, model in enumerate(fast_models, 1):
            current_mark = " ✅" if model == self.current_model else ""
            text += f"{i}. {model.display_name}{current_mark}\n"
            text += f"   提供商: {model.provider}\n"
        
        text += "\n🎯 Pro 模型 (深度分析):\n"
        start_index = len(fast_models) + 1
        for i, model in enumerate(pro_models, start_index):
            current_mark = " ✅" if model == self.current_model else ""
            text += f"{i}. {model.display_name}{current_mark}\n"
            text += f"   提供商: {model.provider}\n"
        
        text += "\n💡 使用方法:\n"
        text += "• /llm {编号} - 切换到指定模型\n"
        text += "• /llm auto - 自动选择模型\n"
        text += "• /llm fast - 使用默认 fast 模型\n"
        text += "• /llm pro - 使用默认 pro 模型\n"
        
        return text
    
    def get_current_model_info(self) -> dict:
        """
        获取当前模型信息
        
        Validates: Requirement 2.4
        """
        if not self.current_model:
            return {}
        
        return {
            'id': self.current_model.id,
            'name': self.current_model.name,
            'display_name': self.current_model.display_name,
            'provider': self.current_model.provider,
            'type': self.current_model.type,
            'max_tokens': self.current_model.max_tokens,
            'temperature': self.current_model.temperature,
            'context_window': self.current_model.context_window,
            'cost_per_1k_tokens': self.current_model.cost_per_1k_tokens,
            'auto_mode': self.auto_mode
        }

# 全局LLM管理器实例
_llm_manager = None

def get_llm_manager() -> LLMManager:
    """获取全局LLM管理器实例"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager
