"""LLM引擎集成模块"""
import asyncio
from typing import Optional, Any
from datetime import datetime

from system_core.ai_engine.llm_client import LLMClient
from system_core.config.llm_manager import get_llm_manager
from system_core.factor_system.config import FactorConfigManager

class FactorLLMAnalyzer:
    """因子LLM分析器 - 使用全局共享的LLM管理器"""
    
    def __init__(self, config: Optional[FactorConfigManager] = None):
        self.config = config or FactorConfigManager()
        # 使用全局共享的LLM管理器,避免重复创建实例
        self.llm_manager = get_llm_manager()
        # LLMClient内部已使用全局管理器,这里保持兼容性
        self.llm_client = LLMClient()
    
    async def analyze_factor_performance(self, factor_id: int, backtest_result: dict[str, Any]) -> dict[str, Any]:
        """分析因子表现"""
        prompt = f"分析因子{factor_id}的回测表现"
        response = await self.llm_client.generate_completion(prompt=prompt, max_tokens=500)
        return {"analysis": response.get("content", ""), "factor_id": factor_id}
