"""
Bot Command Handler for LLM Model Switching

Handles /llm commands from Telegram Bot and provides formatted responses.

Validates: Requirements 2.1-2.5, 3.1-3.5, 4.1-4.5, 5.1-5.3, 10.1, 11.2
"""

import logging
from typing import Optional
from datetime import datetime

from system_core.config.llm_manager import get_llm_manager
from system_core.config.llm_models import ModelConfig

logger = logging.getLogger(__name__)

class BotCommandHandler:
    """
    处理 /llm 相关的 Bot 命令
    
    Validates: Requirements 2.1-2.5, 3.1-3.5, 4.1-4.5, 5.1-5.3, 10.1
    """
    
    def __init__(self):
        """
        初始化处理器
        
        Validates: Requirement 2.1
        """
        self.llm_manager = get_llm_manager()
        logger.info("BotCommandHandler initialized")
    
    async def handle_llm_command(self, args: list[str]) -> str:
        """
        处理 /llm 命令
        
        Args:
            args: 命令参数列表
            
        Returns:
            str: 格式化的响应消息
            
        命令格式:
        - /llm: 显示模型列表
        - /llm {编号}: 切换到指定模型
        - /llm fast|f: 切换到 fast 模型
        - /llm pro|p: 切换到 pro 模型
        - /llm auto|a: 启用自动模式
        - /llm status|stat|s: 显示使用统计
        
        Validates: Requirements 2.1, 3.1, 4.1, 5.1, 10.1
        """
        try:
            # 没有参数 - 显示模型列表
            if not args:
                return self._handle_list_command()
            
            # 获取第一个参数
            command = args[0].lower()
            
            # 尝试解析为数字（模型编号）
            try:
                model_id = int(command)
                return self._handle_switch_by_number(model_id)
            except ValueError:
                pass
            
            # 处理其他命令
            if command in ['fast', 'f']:
                return self._handle_switch_to_fast()
            elif command in ['pro', 'p']:
                return self._handle_switch_to_pro()
            elif command in ['auto', 'a']:
                return self._handle_enable_auto()
            elif command in ['status', 'stat', 's']:
                return self._handle_status()
            else:
                return self._handle_unknown_command(command)
                
        except Exception as e:
            logger.error(f"Error handling /llm command: {e}", exc_info=True)
            return f"❌ 命令处理失败: {str(e)}"
    
    def _handle_list_command(self) -> str:
        """
        处理列表命令 - 显示所有可用模型
        
        Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5
        """
        logger.info("Handling /llm list command")
        return self.llm_manager.get_model_list_text()
    
    def _handle_switch_by_number(self, model_id: int) -> str:
        """
        处理按编号切换命令
        
        Args:
            model_id: 模型编号
            
        Returns:
            格式化的响应消息
            
        Validates: Requirements 3.1, 3.2, 3.3, 3.4, 11.2
        """
        logger.info(f"Handling /llm {model_id} command")
        
        success, message, old_model = self.llm_manager.switch_model(model_id)
        
        if success:
            new_model = self.llm_manager.current_model
            return self.format_switch_message(old_model, new_model)
        else:
            # 错误提示 - Validates: Requirement 3.2, 11.2
            return f"❌ {message}"
    
    def _handle_switch_to_fast(self) -> str:
        """
        处理切换到 fast 模型命令
        
        Validates: Requirements 4.1, 4.3, 4.4, 11.2
        """
        logger.info("Handling /llm fast command")
        
        success, message, old_model = self.llm_manager.switch_to_fast()
        
        if success:
            new_model = self.llm_manager.current_model
            return self._format_fast_switch_message(new_model)
        else:
            return f"❌ {message}"
    
    def _handle_switch_to_pro(self) -> str:
        """
        处理切换到 pro 模型命令
        
        Validates: Requirements 4.2, 4.3, 4.4, 11.2
        """
        logger.info("Handling /llm pro command")
        
        success, message, old_model = self.llm_manager.switch_to_pro()
        
        if success:
            new_model = self.llm_manager.current_model
            return self._format_pro_switch_message(new_model)
        else:
            return f"❌ {message}"
    
    def _handle_enable_auto(self) -> str:
        """
        处理启用自动模式命令
        
        Validates: Requirements 5.1, 5.2, 5.3
        """
        logger.info("Handling /llm auto command")
        
        success, message = self.llm_manager.enable_auto_mode()
        
        if success:
            return self.format_auto_mode_message()
        else:
            return f"❌ {message}"
    
    def _handle_status(self) -> str:
        """
        处理状态查询命令
        
        Validates: Requirements 10.1, 10.3
        """
        logger.info("Handling /llm status command")
        
        stats = self.llm_manager.get_statistics()
        return self.format_statistics(stats)
    
    def _handle_unknown_command(self, command: str) -> str:
        """
        处理未知命令
        
        Validates: Requirement 11.2
        """
        logger.warning(f"Unknown /llm command: {command}")
        
        return (
            f"❌ 未知命令: {command}\n\n"
            "💡 可用命令:\n"
            "• /llm - 查看模型列表\n"
            "• /llm {编号} - 切换到指定模型\n"
            "• /llm fast - 切换到 fast 模型\n"
            "• /llm pro - 切换到 pro 模型\n"
            "• /llm auto - 启用自动模式\n"
            "• /llm status - 查看使用统计"
        )
    
    def format_switch_message(
        self,
        old_model: Optional[ModelConfig],
        new_model: ModelConfig
    ) -> str:
        """
        格式化切换成功消息
        
        Args:
            old_model: 切换前的模型
            new_model: 切换后的模型
            
        Returns:
            格式化的消息
            
        Validates: Requirements 3.3, 4.4
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        text = "🧠 切换大模型\n\n"
        
        if old_model:
            text += f"从: {old_model.display_name} ({old_model.type})\n"
        
        text += f"到: {new_model.display_name} ({new_model.type})\n\n"
        
        text += "📊 模型信息:\n"
        text += f"• 提供商: {new_model.provider}\n"
        text += f"• 类型: {new_model.type}\n"
        text += f"• 上下文窗口: {new_model.context_window} tokens\n"
        text += f"• 成本: ${new_model.cost_per_1k_tokens}/1K tokens\n\n"
        
        text += "✅ 切换成功\n\n"
        text += f"⏰ {timestamp}"
        
        return text
    
    def _format_fast_switch_message(self, new_model: ModelConfig) -> str:
        """
        格式化 fast 模型切换消息
        
        Validates: Requirement 4.4
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        text = "⚡ 切换到 Fast 模型\n\n"
        text += f"{new_model.display_name}\n"
        text += f"• 提供商: {new_model.provider}\n"
        text += f"• 特点: 快速响应，适合简单任务\n\n"
        text += "✅ 切换成功\n\n"
        text += f"⏰ {timestamp}"
        
        return text
    
    def _format_pro_switch_message(self, new_model: ModelConfig) -> str:
        """
        格式化 pro 模型切换消息
        
        Validates: Requirement 4.4
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        text = "🎯 切换到 Pro 模型\n\n"
        text += f"{new_model.display_name}\n"
        text += f"• 提供商: {new_model.provider}\n"
        text += f"• 特点: 深度分析，适合复杂任务\n\n"
        text += "✅ 切换成功\n\n"
        text += f"⏰ {timestamp}"
        
        return text
    
    def format_auto_mode_message(self) -> str:
        """
        格式化自动模式启用消息
        
        Validates: Requirements 5.2, 5.3
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        auto_config = self.llm_manager.config.get('auto_selection', {})
        strategy = auto_config.get('strategy', 'adaptive')
        
        text = "🤖 自动模型选择\n\n"
        text += "✅ 已启用自动选择模式\n\n"
        text += f"📋 选择策略: {strategy}\n\n"
        
        if strategy == "adaptive":
            adaptive_config = auto_config.get('adaptive', {})
            length_threshold = adaptive_config.get('length_threshold', 1000)
            
            text += "🎯 自适应策略:\n"
            text += "• 简单任务 → Fast 模型\n"
            text += "• 复杂任务 → Pro 模型\n"
            text += f"• 短文本 (< {length_threshold} 字符) → Fast\n"
            text += f"• 长文本 (≥ {length_threshold} 字符) → Pro\n"
            
        elif strategy == "cost_optimized":
            text += "💰 成本优化策略:\n"
            text += "• 优先使用 Fast 模型\n"
            text += "• 仅在必要时使用 Pro 模型\n"
            
        elif strategy == "performance_optimized":
            text += "⚡ 性能优化策略:\n"
            text += "• 优先使用 Pro 模型\n"
            text += "• 仅简单任务使用 Fast 模型\n"
        
        text += "\n💡 系统将根据任务自动选择最合适的模型\n\n"
        text += f"⏰ {timestamp}"
        
        return text
    
    def format_statistics(self, stats: dict) -> str:
        """
        格式化统计信息
        
        Args:
            stats: 统计数据字典
            
        Returns:
            格式化的统计信息
            
        Validates: Requirements 10.1, 10.3
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        text = "📊 LLM 使用统计\n\n"
        text += f"📌 当前模型: {stats.get('current_model', 'Unknown')}\n\n"
        
        # 今日统计
        daily = stats.get('daily', {})
        if 'total' in daily:
            total = daily['total']
            text += "📈 今日使用:\n"
            text += f"• 请求次数: {total.get('request_count', 0)}\n"
            text += f"• Token 消耗: {total.get('total_tokens', 0)}\n"
            text += f"• 预估成本: ${total.get('total_cost', 0):.4f}\n\n"
        
        # 本月统计
        monthly = stats.get('monthly', {})
        if 'total' in monthly:
            total = monthly['total']
            text += "📅 本月使用:\n"
            text += f"• 请求次数: {total.get('request_count', 0)}\n"
            text += f"• Token 消耗: {total.get('total_tokens', 0)}\n"
            text += f"• 预估成本: ${total.get('total_cost', 0):.4f}\n\n"
        
        text += f"⏰ {timestamp}"
        
        return text

# 全局处理器实例
_bot_handler = None

def get_bot_handler() -> BotCommandHandler:
    """获取全局 Bot 命令处理器实例"""
    global _bot_handler
    if _bot_handler is None:
        _bot_handler = BotCommandHandler()
    return _bot_handler
