"""
止损处理器
Stop Loss Handler

处理止损逻辑和强制平仓
"""

from typing import Dict, Any, Optional
from datetime import datetime

from system_core.config import get_logger
from system_core.event_bus import EventBus

logger = get_logger(__name__)


class StopLossHandler:
    """止损处理器"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus
        self.stop_loss_history: list = []
        
    async def execute_stop_loss(
        self,
        order_id: str,
        symbol: str,
        entry_price: float,
        current_price: float,
        quantity: float,
        reason: str
    ) -> Dict[str, Any]:
        """执行止损"""
        
        # 计算亏损
        pnl = (current_price - entry_price) * quantity
        pnl_percentage = (current_price - entry_price) / entry_price
        
        # 记录止损
        stop_loss_record = {
            "order_id": order_id,
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": current_price,
            "quantity": quantity,
            "pnl": pnl,
            "pnl_percentage": pnl_percentage,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "status": "executed"
        }
        
        self.stop_loss_history.append(stop_loss_record)
        
        logger.warning(
            "stop_loss_executed",
            order_id=order_id,
            symbol=symbol,
            pnl=pnl,
            pnl_percentage=pnl_percentage
        )
        
        # 发送平仓事件
        if self.event_bus:
            await self.event_bus.publish("order.close", {
                "order_id": order_id,
                "symbol": symbol,
                "action": "close",
                "quantity": quantity,
                "price": current_price,
                "reason": "stop_loss",
                "details": stop_loss_record
            })
            
            # 发送通知
            await self.event_bus.publish("notification.send", {
                "type": "stop_loss_executed",
                "title": "止损已执行",
                "message": f"{symbol} 触发止损，亏损 {abs(pnl_percentage)*100:.1f}%",
                "data": stop_loss_record,
                "priority": "high"
            })
        
        return stop_loss_record
    
    def get_stop_loss_statistics(self) -> Dict[str, Any]:
        """获取止损统计"""
        if not self.stop_loss_history:
            return {
                "total_count": 0,
                "total_loss": 0.0,
                "average_loss_percentage": 0.0
            }
        
        total_count = len(self.stop_loss_history)
        total_loss = sum(record["pnl"] for record in self.stop_loss_history)
        average_loss_percentage = sum(
            record["pnl_percentage"] for record in self.stop_loss_history
        ) / total_count
        
        return {
            "total_count": total_count,
            "total_loss": total_loss,
            "average_loss_percentage": average_loss_percentage,
            "recent_stops": self.stop_loss_history[-10:]  # 最近10次
        }
