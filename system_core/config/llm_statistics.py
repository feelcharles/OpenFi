"""
LLM Usage Statistics Tracker

This module tracks usage statistics for LLM models including request counts,
token consumption, and estimated costs.

Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

class UsageStatistics:
    """
    使用统计追踪器
    
    追踪每个模型的使用情况，包括请求次数、token 消耗和成本。
    支持今日和本月统计，并在每日零点自动重置今日统计。
    
    Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5
    """
    
    def __init__(self, storage_path: str = "user_data/llm_statistics.json"):
        """
        初始化统计数据
        
        Args:
            storage_path: 统计数据存储路径
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 统计数据结构
        self.daily_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
            'request_count': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'last_used': None
        })
        
        self.monthly_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
            'request_count': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'last_used': None
        })
        
        # 记录当前日期和月份
        self.current_date = date.today()
        self.current_month = (self.current_date.year, self.current_date.month)
        
        # 加载持久化数据
        self._load_from_disk()
        
        logger.info(f"UsageStatistics initialized with storage at {self.storage_path}")
    
    def record_request(
        self,
        model_name: str,
        tokens_used: int,
        cost: float
    ):
        """
        记录一次请求
        
        Args:
            model_name: 模型名称
            tokens_used: 使用的 token 数
            cost: 本次请求成本
            
        Validates: Requirement 10.2, 10.4
        """
        # 检查是否需要重置今日统计
        self._check_and_reset_daily()
        
        # 检查是否需要重置本月统计
        self._check_and_reset_monthly()
        
        # 更新今日统计
        self.daily_stats[model_name]['request_count'] += 1
        self.daily_stats[model_name]['total_tokens'] += tokens_used
        self.daily_stats[model_name]['total_cost'] += cost
        self.daily_stats[model_name]['last_used'] = datetime.now().isoformat()
        
        # 更新本月统计
        self.monthly_stats[model_name]['request_count'] += 1
        self.monthly_stats[model_name]['total_tokens'] += tokens_used
        self.monthly_stats[model_name]['total_cost'] += cost
        self.monthly_stats[model_name]['last_used'] = datetime.now().isoformat()
        
        logger.debug(
            f"Recorded request for {model_name}: {tokens_used} tokens, ${cost:.4f}"
        )
        
        # 持久化到磁盘
        self._save_to_disk()
    
    def get_daily_stats(self, model_name: Optional[str] = None) -> dict[str, Any]:
        """
        获取今日统计
        
        Args:
            model_name: 模型名称，如果为 None 则返回所有模型的统计
            
        Returns:
            Dict: 统计数据
            
        Validates: Requirement 10.1, 10.3
        """
        self._check_and_reset_daily()
        
        if model_name:
            return dict(self.daily_stats.get(model_name, {
                'request_count': 0,
                'total_tokens': 0,
                'total_cost': 0.0,
                'last_used': None
            }))
        
        # 返回所有模型的统计
        return {
            'models': dict(self.daily_stats),
            'total': self._aggregate_stats(self.daily_stats)
        }
    
    def get_monthly_stats(self, model_name: Optional[str] = None) -> dict[str, Any]:
        """
        获取本月统计
        
        Args:
            model_name: 模型名称，如果为 None 则返回所有模型的统计
            
        Returns:
            Dict: 统计数据
            
        Validates: Requirement 10.1, 10.3
        """
        self._check_and_reset_monthly()
        
        if model_name:
            return dict(self.monthly_stats.get(model_name, {
                'request_count': 0,
                'total_tokens': 0,
                'total_cost': 0.0,
                'last_used': None
            }))
        
        # 返回所有模型的统计
        return {
            'models': dict(self.monthly_stats),
            'total': self._aggregate_stats(self.monthly_stats)
        }
    
    def reset_daily_stats(self):
        """
        重置今日统计（每日零点调用）
        
        Validates: Requirement 10.5
        """
        logger.info("Resetting daily statistics")
        self.daily_stats.clear()
        self.current_date = date.today()
        self._save_to_disk()
    
    def reset_monthly_stats(self):
        """
        重置本月统计（每月1号零点调用）
        
        Validates: Requirement 10.5
        """
        logger.info("Resetting monthly statistics")
        self.monthly_stats.clear()
        self.current_month = (date.today().year, date.today().month)
        self._save_to_disk()
    
    def _check_and_reset_daily(self):
        """检查是否需要重置今日统计"""
        today = date.today()
        if today != self.current_date:
            logger.info(f"Date changed from {self.current_date} to {today}, resetting daily stats")
            self.reset_daily_stats()
    
    def _check_and_reset_monthly(self):
        """检查是否需要重置本月统计"""
        today = date.today()
        current_month = (today.year, today.month)
        if current_month != self.current_month:
            logger.info(
                f"Month changed from {self.current_month} to {current_month}, "
                "resetting monthly stats"
            )
            self.reset_monthly_stats()
    
    def _aggregate_stats(self, stats_dict: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """聚合所有模型的统计数据"""
        total_requests = sum(s['request_count'] for s in stats_dict.values())
        total_tokens = sum(s['total_tokens'] for s in stats_dict.values())
        total_cost = sum(s['total_cost'] for s in stats_dict.values())
        
        return {
            'request_count': total_requests,
            'total_tokens': total_tokens,
            'total_cost': total_cost
        }
    
    def _save_to_disk(self):
        """持久化统计数据到磁盘"""
        try:
            data = {
                'current_date': self.current_date.isoformat(),
                'current_month': list(self.current_month),
                'daily_stats': dict(self.daily_stats),
                'monthly_stats': dict(self.monthly_stats)
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Statistics saved to {self.storage_path}")
            
        except Exception as e:
            logger.error(f"Failed to save statistics to disk: {e}", exc_info=True)
    
    def _load_from_disk(self):
        """从磁盘加载统计数据"""
        try:
            if not self.storage_path.exists():
                logger.info("No existing statistics file found, starting fresh")
                return
            
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 恢复日期信息
            saved_date = date.fromisoformat(data.get('current_date', date.today().isoformat()))
            saved_month = tuple(data.get('current_month', [date.today().year, date.today().month]))
            
            # 检查是否需要重置
            today = date.today()
            current_month = (today.year, today.month)
            
            # 如果是同一天，恢复今日统计
            if saved_date == today:
                self.daily_stats = defaultdict(
                    lambda: {'request_count': 0, 'total_tokens': 0, 'total_cost': 0.0, 'last_used': None},
                    data.get('daily_stats', {})
                )
                logger.info("Loaded daily statistics from disk")
            else:
                logger.info(f"Date changed, daily statistics reset")
            
            # 如果是同一月，恢复本月统计
            if saved_month == current_month:
                self.monthly_stats = defaultdict(
                    lambda: {'request_count': 0, 'total_tokens': 0, 'total_cost': 0.0, 'last_used': None},
                    data.get('monthly_stats', {})
                )
                logger.info("Loaded monthly statistics from disk")
            else:
                logger.info(f"Month changed, monthly statistics reset")
            
        except Exception as e:
            logger.error(f"Failed to load statistics from disk: {e}", exc_info=True)

# 全局统计实例
_usage_statistics = None

def get_usage_statistics() -> UsageStatistics:
    """获取全局统计实例"""
    global _usage_statistics
    if _usage_statistics is None:
        _usage_statistics = UsageStatistics()
    return _usage_statistics
