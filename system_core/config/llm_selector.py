"""
LLM Model Selection Strategies

This module implements different strategies for automatically selecting
the most appropriate LLM model based on task characteristics.

Validates: Requirements 5.4, 6.1-6.5, 7.1-7.5, 8.1-8.5
"""

from typing import Optional, Any
import logging
from system_core.config.llm_models import ModelConfig

logger = logging.getLogger(__name__)

class AdaptiveStrategy:
    """
    自适应选择策略
    
    根据任务类型和输入长度智能选择模型。
    简单任务或短文本使用 fast 模型，复杂任务或长文本使用 pro 模型。
    
    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
    """
    
    def select(
        self,
        models: list[ModelConfig],
        task_type: Optional[str],
        input_length: Optional[int],
        config: dict[str, Any]
    ) -> ModelConfig:
        """
        根据任务类型和输入长度选择模型
        
        规则:
        1. 如果任务类型在 simple_tasks 列表中，选择 fast 模型
        2. 如果任务类型在 complex_tasks 列表中，选择 pro 模型
        3. 如果输入长度 < length_threshold，选择 fast 模型
        4. 如果输入长度 >= length_threshold，选择 pro 模型
        5. 默认选择第一个 fast 模型
        
        Args:
            models: 可用模型列表
            task_type: 任务类型（如 "translation", "analysis"）
            input_length: 输入文本长度
            config: 策略配置
            
        Returns:
            ModelConfig: 选择的模型
        """
        simple_tasks = config.get('simple_tasks', [])
        complex_tasks = config.get('complex_tasks', [])
        length_threshold = config.get('length_threshold', 1000)
        
        # 获取 fast 和 pro 模型列表
        fast_models = [m for m in models if m.type == 'fast']
        pro_models = [m for m in models if m.type == 'pro']
        
        # 规则 1: 简单任务使用 fast 模型
        if task_type and task_type in simple_tasks:
            if fast_models:
                logger.debug(
                    f"Adaptive strategy: Selected fast model for simple task '{task_type}'"
                )
                return fast_models[0]
        
        # 规则 2: 复杂任务使用 pro 模型
        if task_type and task_type in complex_tasks:
            if pro_models:
                logger.debug(
                    f"Adaptive strategy: Selected pro model for complex task '{task_type}'"
                )
                return pro_models[0]
        
        # 规则 3: 短文本使用 fast 模型
        if input_length is not None and input_length < length_threshold:
            if fast_models:
                logger.debug(
                    f"Adaptive strategy: Selected fast model for short input ({input_length} < {length_threshold})"
                )
                return fast_models[0]
        
        # 规则 4: 长文本使用 pro 模型
        if input_length is not None and input_length >= length_threshold:
            if pro_models:
                logger.debug(
                    f"Adaptive strategy: Selected pro model for long input ({input_length} >= {length_threshold})"
                )
                return pro_models[0]
        
        # 规则 5: 默认使用第一个 fast 模型
        if fast_models:
            logger.debug("Adaptive strategy: Using default fast model")
            return fast_models[0]
        
        # 如果没有 fast 模型，使用第一个 pro 模型
        if pro_models:
            logger.warning("Adaptive strategy: No fast models available, using pro model")
            return pro_models[0]
        
        # 如果都没有，返回第一个可用模型
        if models:
            logger.warning("Adaptive strategy: No typed models available, using first model")
            return models[0]
        
        raise ValueError("No models available for selection")

class CostOptimizedStrategy:
    """
    成本优化策略
    
    优先选择成本最低的模型，在保证任务完成的前提下最小化成本。
    
    Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5
    """
    
    def select(
        self,
        models: list[ModelConfig],
        task_type: Optional[str],
        input_length: Optional[int],
        config: dict[str, Any]
    ) -> ModelConfig:
        """
        优先选择成本最低的模型
        
        规则:
        1. 按 cost_per_1k_tokens 排序
        2. 如果任务复杂度超过阈值，从 pro 模型中选择成本最低的
        3. 否则从 fast 模型中选择成本最低的
        4. 未配置成本的模型视为成本无穷大
        
        Args:
            models: 可用模型列表
            task_type: 任务类型
            input_length: 输入长度
            config: 策略配置
            
        Returns:
            ModelConfig: 选择的模型
        """
        if not models:
            raise ValueError("No models available for selection")
        
        prefer_fast = config.get('prefer_fast', True)
        pro_threshold = config.get('pro_threshold', 0.8)
        
        # 获取 fast 和 pro 模型列表
        fast_models = [m for m in models if m.type == 'fast']
        pro_models = [m for m in models if m.type == 'pro']
        
        # 简单的复杂度评估（可以根据需要扩展）
        complexity = 0.5  # 默认中等复杂度
        if input_length and input_length > 2000:
            complexity = 0.9
        elif input_length and input_length < 500:
            complexity = 0.3
        
        # 根据复杂度选择模型类型
        if complexity >= pro_threshold and pro_models:
            # 高复杂度任务，从 pro 模型中选择成本最低的
            selected = min(pro_models, key=lambda m: m.cost_per_1k_tokens)
            logger.debug(
                f"Cost-optimized strategy: Selected pro model '{selected.display_name}' "
                f"(cost: ${selected.cost_per_1k_tokens}/1K tokens, complexity: {complexity})"
            )
            return selected
        
        # 低复杂度任务，从 fast 模型中选择成本最低的
        if fast_models:
            selected = min(fast_models, key=lambda m: m.cost_per_1k_tokens)
            logger.debug(
                f"Cost-optimized strategy: Selected fast model '{selected.display_name}' "
                f"(cost: ${selected.cost_per_1k_tokens}/1K tokens)"
            )
            return selected
        
        # 如果没有 fast 模型，从所有模型中选择成本最低的
        selected = min(models, key=lambda m: m.cost_per_1k_tokens)
        logger.warning(
            f"Cost-optimized strategy: No fast models available, "
            f"selected '{selected.display_name}' (cost: ${selected.cost_per_1k_tokens}/1K tokens)"
        )
        return selected

class PerformanceOptimizedStrategy:
    """
    性能优化策略
    
    优先选择性能最好的模型，以获得最佳的输出质量。
    
    Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5
    """
    
    def select(
        self,
        models: list[ModelConfig],
        task_type: Optional[str],
        input_length: Optional[int],
        config: dict[str, Any]
    ) -> ModelConfig:
        """
        优先选择性能最好的模型
        
        规则:
        1. 优先选择 pro 模型（性能更好）
        2. 如果任务复杂度低于阈值，选择 fast 模型
        3. 同类型中选择列表中第一个模型
        
        Args:
            models: 可用模型列表
            task_type: 任务类型
            input_length: 输入长度
            config: 策略配置
            
        Returns:
            ModelConfig: 选择的模型
        """
        if not models:
            raise ValueError("No models available for selection")
        
        prefer_pro = config.get('prefer_pro', True)
        fast_threshold = config.get('fast_threshold', 0.3)
        
        # 获取 fast 和 pro 模型列表
        fast_models = [m for m in models if m.type == 'fast']
        pro_models = [m for m in models if m.type == 'pro']
        
        # 简单的复杂度评估
        complexity = 0.5  # 默认中等复杂度
        if input_length and input_length < 500:
            complexity = 0.2
        elif input_length and input_length > 2000:
            complexity = 0.9
        
        # 根据复杂度选择模型类型
        if complexity < fast_threshold and fast_models:
            # 低复杂度任务，使用 fast 模型
            selected = fast_models[0]
            logger.debug(
                f"Performance-optimized strategy: Selected fast model '{selected.display_name}' "
                f"for simple task (complexity: {complexity})"
            )
            return selected
        
        # 默认使用 pro 模型（性能优先）
        if pro_models:
            selected = pro_models[0]
            logger.debug(
                f"Performance-optimized strategy: Selected pro model '{selected.display_name}' "
                f"for optimal performance"
            )
            return selected
        
        # 如果没有 pro 模型，使用 fast 模型
        if fast_models:
            selected = fast_models[0]
            logger.warning(
                f"Performance-optimized strategy: No pro models available, "
                f"using fast model '{selected.display_name}'"
            )
            return selected
        
        # 如果都没有，返回第一个可用模型
        selected = models[0]
        logger.warning(
            f"Performance-optimized strategy: No typed models available, "
            f"using first model '{selected.display_name}'"
        )
        return selected

class ModelSelector:
    """
    模型选择器，实现自动选择策略
    
    根据配置的策略类型，委托给具体的策略实现。
    
    Validates: Requirement 5.4
    """
    
    def __init__(self, strategy_config: dict[str, Any]):
        """
        初始化选择器，加载策略配置
        
        Args:
            strategy_config: 策略配置字典
        """
        self.strategy_config = strategy_config
        self.strategy_name = strategy_config.get('strategy', 'adaptive')
        
        # 创建策略实例
        self.strategies = {
            'adaptive': AdaptiveStrategy(),
            'cost_optimized': CostOptimizedStrategy(),
            'performance_optimized': PerformanceOptimizedStrategy()
        }
        
        logger.info(f"ModelSelector initialized with strategy: {self.strategy_name}")
    
    def select(
        self,
        models: list[ModelConfig],
        task_type: Optional[str] = None,
        input_length: Optional[int] = None
    ) -> ModelConfig:
        """
        根据策略选择模型
        
        Args:
            models: 可用模型列表
            task_type: 任务类型
            input_length: 输入长度
            
        Returns:
            ModelConfig: 选择的模型
            
        Raises:
            ValueError: 如果没有可用模型或策略不存在
        """
        if not models:
            raise ValueError("No models available for selection")
        
        # 获取策略实例
        strategy = self.strategies.get(self.strategy_name)
        if not strategy:
            logger.warning(
                f"Unknown strategy '{self.strategy_name}', falling back to adaptive"
            )
            strategy = self.strategies['adaptive']
        
        # 获取策略特定的配置
        strategy_config = self.strategy_config.get(self.strategy_name, {})
        
        # 委托给具体策略
        selected_model = strategy.select(models, task_type, input_length, strategy_config)
        
        logger.info(
            f"Selected model: {selected_model.display_name} "
            f"(strategy: {self.strategy_name}, task: {task_type}, length: {input_length})"
        )
        
        return selected_model
