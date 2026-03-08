"""
仓位监控器
Position Monitor

实时监控所有持仓的风险状态
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

from system_core.config import get_logger

logger = get_logger(__name__)


@dataclass
class Position:
    """持仓信息"""
    order_id: str
    symbol: str
    action: str  # buy/sell
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_percentage: float = 0.0
    status: str = "open"  # open/closed
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_price(self, new_price: float):
        """更新价格并计算盈亏"""
        self.current_price = new_price
        
        if self.action == "buy":
            self.pnl = (new_price - self.entry_price) * self.quantity
            self.pnl_percentage = (new_price - self.entry_price) / self.entry_price
        else:  # sell/short
            self.pnl = (self.entry_price - new_price) * self.quantity
            self.pnl_percentage = (self.entry_price - new_price) / self.entry_price
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "action": self.action,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "current_price": self.current_price,
            "pnl": self.pnl,
            "pnl_percentage": self.pnl_percentage,
            "status": self.status,
            "metadata": self.metadata
        }


class PositionMonitor:
    """仓位监控器"""
    
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.monitoring = False
        
    def add_position(
        self,
        order_id: str,
        symbol: str,
        action: str,
        quantity: float,
        entry_price: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Position:
        """添加持仓"""
        position = Position(
            order_id=order_id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            entry_price=entry_price,
            entry_time=datetime.now(),
            current_price=entry_price,
            metadata=metadata or {}
        )
        
        self.positions[order_id] = position
        
        logger.info(
            "position_added",
            order_id=order_id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            entry_price=entry_price
        )
        
        return position
    
    def update_position_price(self, order_id: str, new_price: float):
        """更新持仓价格"""
        if order_id in self.positions:
            self.positions[order_id].update_price(new_price)
    
    def update_symbol_prices(self, symbol: str, new_price: float):
        """更新某个标的所有持仓的价格"""
        for position in self.positions.values():
            if position.symbol == symbol:
                position.update_price(new_price)
    
    def close_position(self, order_id: str, close_price: Optional[float] = None) -> Optional[Position]:
        """关闭持仓"""
        if order_id not in self.positions:
            logger.warning("position_not_found", order_id=order_id)
            return None
        
        position = self.positions[order_id]
        
        if close_price:
            position.update_price(close_price)
        
        position.status = "closed"
        
        # 移到已关闭列表
        self.closed_positions.append(position)
        del self.positions[order_id]
        
        logger.info(
            "position_closed",
            order_id=order_id,
            symbol=position.symbol,
            pnl=position.pnl,
            pnl_percentage=position.pnl_percentage
        )
        
        return position
    
    def get_position(self, order_id: str) -> Optional[Position]:
        """获取持仓"""
        return self.positions.get(order_id)
    
    def get_all_positions(self) -> List[Position]:
        """获取所有持仓"""
        return list(self.positions.values())
    
    def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """获取某个标的的所有持仓"""
        return [pos for pos in self.positions.values() if pos.symbol == symbol]
    
    def get_total_pnl(self) -> float:
        """获取总盈亏"""
        return sum(pos.pnl for pos in self.positions.values())
    
    def get_total_exposure(self) -> float:
        """获取总敞口"""
        return sum(
            abs(pos.quantity * pos.current_price)
            for pos in self.positions.values()
        )
    
    def get_positions_at_risk(self, threshold: float = -0.15) -> List[Position]:
        """获取有风险的持仓（默认亏损15%以上）"""
        return [
            pos for pos in self.positions.values()
            if pos.pnl_percentage <= threshold
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        open_positions = list(self.positions.values())
        
        if not open_positions:
            return {
                "open_count": 0,
                "closed_count": len(self.closed_positions),
                "total_pnl": 0.0,
                "total_exposure": 0.0,
                "positions_at_risk": 0
            }
        
        total_pnl = sum(pos.pnl for pos in open_positions)
        total_exposure = sum(abs(pos.quantity * pos.current_price) for pos in open_positions)
        positions_at_risk = len(self.get_positions_at_risk())
        
        # 计算已关闭持仓的统计
        closed_pnl = sum(pos.pnl for pos in self.closed_positions)
        winning_trades = sum(1 for pos in self.closed_positions if pos.pnl > 0)
        losing_trades = sum(1 for pos in self.closed_positions if pos.pnl < 0)
        
        return {
            "open_count": len(open_positions),
            "closed_count": len(self.closed_positions),
            "total_pnl": total_pnl,
            "total_exposure": total_exposure,
            "positions_at_risk": positions_at_risk,
            "closed_pnl": closed_pnl,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": winning_trades / len(self.closed_positions) if self.closed_positions else 0.0
        }
    
    async def start_monitoring(self, check_interval: int = 5):
        """启动监控"""
        self.monitoring = True
        logger.info("position_monitoring_started", check_interval=check_interval)
        
        while self.monitoring:
            try:
                # 检查所有持仓
                stats = self.get_statistics()
                
                if stats["positions_at_risk"] > 0:
                    logger.warning(
                        "positions_at_risk_detected",
                        count=stats["positions_at_risk"],
                        total_pnl=stats["total_pnl"]
                    )
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("monitoring_error", error=str(e))
                await asyncio.sleep(check_interval)
        
        logger.info("position_monitoring_stopped")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
