"""
风险管理器
Risk Manager

负责整体风险控制策略的协调和执行
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from system_core.config import get_logger, ConfigurationManager
from system_core.event_bus import EventBus

logger = get_logger(__name__)


@dataclass
class RiskConfig:
    """风险配置"""
    stop_loss_threshold: float = 0.20
    stop_profit_threshold: float = 0.30
    max_position_size: float = 0.10
    max_total_exposure: float = 0.80
    daily_loss_limit: float = 0.05
    max_drawdown_percent: float = 0.20  # 最大回撤百分比
    force_close_on_max_drawdown: bool = True  # 达到最大回撤时强制平仓
    force_close_enabled: bool = True
    position_check_interval: float = 5.0  # 持仓检查间隔（秒）
    drawdown_check_interval: float = 1.0  # 回撤检查间隔（秒）
    high_frequency_mode: bool = False  # 高频模式
    use_event_driven: bool = False  # 使用事件驱动


class RiskManager:
    """风险管理器"""
    
    def __init__(self, event_bus: Optional[EventBus] = None, account_id: Optional[str] = None):
        self.event_bus = event_bus
        self.account_id = account_id
        self.config: Optional[RiskConfig] = None
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.daily_pnl: float = 0.0
        self.peak_equity: float = 0.0  # 峰值权益
        self.current_equity: float = 0.0  # 当前权益
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False
        self.drawdown_monitoring_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """初始化风险管理器"""
        # 加载配置
        config_manager = ConfigurationManager()
        await config_manager.initialize()
        
        # 如果指定了账户ID，从账户配置加载
        if self.account_id:
            accounts_config = config_manager.get_config("accounts.yaml")
            if accounts_config and "accounts" in accounts_config:
                for account in accounts_config["accounts"]:
                    if account["account_id"] == self.account_id:
                        rm = account.get("risk_management", {})
                        self.config = RiskConfig(
                            stop_loss_threshold=rm.get("max_daily_loss_percent", 20.0) / 100.0,
                            stop_profit_threshold=0.30,
                            max_position_size=rm.get("max_total_risk_percent", 20.0) / 100.0,
                            max_total_exposure=0.80,
                            daily_loss_limit=rm.get("max_daily_loss_percent", 5.0) / 100.0,
                            max_drawdown_percent=rm.get("max_drawdown_percent", 20.0) / 100.0,
                            force_close_on_max_drawdown=rm.get("force_close_on_max_drawdown", True),
                            force_close_enabled=True,
                            position_check_interval=5.0,
                            drawdown_check_interval=1.0,
                            high_frequency_mode=False,
                            use_event_driven=False
                        )
                        break
        
        # 如果没有从账户配置加载，使用全局风险配置
        if not self.config:
            risk_config = config_manager.get_config("risk_config.yaml")
            if risk_config and "risk_control" in risk_config:
                rc = risk_config["risk_control"]
                monitoring = rc.get("monitoring", {})
                hf_mode = rc.get("high_frequency_mode", {})
                
                # 检查是否启用高频模式
                is_hf_enabled = hf_mode.get("enabled", False)
                
                self.config = RiskConfig(
                    stop_loss_threshold=rc.get("stop_loss", {}).get("threshold", 0.20),
                    stop_profit_threshold=rc.get("stop_profit", {}).get("threshold", 0.30),
                    max_position_size=rc.get("position_management", {}).get("max_position_size", 0.10),
                    max_total_exposure=rc.get("position_management", {}).get("max_total_exposure", 0.80),
                    daily_loss_limit=rc.get("account_protection", {}).get("daily_loss_limit", 0.05),
                    max_drawdown_percent=0.20,
                    force_close_on_max_drawdown=True,
                    force_close_enabled=rc.get("stop_loss", {}).get("force_close", True),
                    position_check_interval=hf_mode.get("position_check_interval", monitoring.get("position_check_interval", 5.0)) if is_hf_enabled else monitoring.get("position_check_interval", 5.0),
                    drawdown_check_interval=hf_mode.get("drawdown_check_interval", monitoring.get("drawdown_check_interval", 1.0)) if is_hf_enabled else monitoring.get("drawdown_check_interval", 1.0),
                    high_frequency_mode=is_hf_enabled,
                    use_event_driven=hf_mode.get("use_event_driven", False) if is_hf_enabled else False
                )
            else:
                self.config = RiskConfig()
        
        await config_manager.close()
        
        # 订阅事件
        if self.event_bus:
            await self.event_bus.subscribe("execution.start", self._on_execution_start)
            await self.event_bus.subscribe("position.update", self._on_position_update)
            await self.event_bus.subscribe("market.price_update", self._on_price_update)
            await self.event_bus.subscribe("account.equity_update", self._on_equity_update)
        
        self.is_running = True
        
        # 启动回撤监控任务
        if self.config.force_close_on_max_drawdown:
            self.drawdown_monitoring_task = asyncio.create_task(self._monitor_drawdown())
        
        logger.info(
            "risk_manager_initialized",
            account_id=self.account_id,
            config=self.config,
            mode="high_frequency" if self.config.high_frequency_mode else "normal"
        )
    
    async def close(self):
        """关闭风险管理器"""
        self.is_running = False
        
        # 取消回撤监控任务
        if self.drawdown_monitoring_task:
            self.drawdown_monitoring_task.cancel()
            try:
                await self.drawdown_monitoring_task
            except asyncio.CancelledError:
                pass
        
        # 取消所有监控任务
        for task in self.monitoring_tasks.values():
            task.cancel()
        
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks.values(), return_exceptions=True)
        
        # 取消订阅
        if self.event_bus:
            await self.event_bus.unsubscribe("execution.start", self._on_execution_start)
            await self.event_bus.unsubscribe("position.update", self._on_position_update)
            await self.event_bus.unsubscribe("market.price_update", self._on_price_update)
            await self.event_bus.unsubscribe("account.equity_update", self._on_equity_update)
        
        logger.info("risk_manager_closed")
    
    async def _on_execution_start(self, event):
        """处理交易执行事件"""
        payload = event.payload
        order_id = payload.get("order_id")
        
        if not order_id:
            return
        
        # 记录持仓
        self.positions[order_id] = {
            "symbol": payload.get("symbol"),
            "action": payload.get("action"),
            "quantity": payload.get("quantity"),
            "entry_price": payload.get("entry_price"),
            "entry_time": datetime.now(),
            "current_price": payload.get("entry_price"),
            "pnl": 0.0,
            "pnl_percentage": 0.0
        }
        
        # 启动监控任务
        if order_id not in self.monitoring_tasks:
            task = asyncio.create_task(self._monitor_position(order_id))
            self.monitoring_tasks[order_id] = task
        
        logger.info("position_opened", order_id=order_id, symbol=payload.get("symbol"))
    
    async def _on_position_update(self, event):
        """处理持仓更新事件"""
        payload = event.payload
        order_id = payload.get("order_id")
        
        if order_id in self.positions:
            self.positions[order_id].update(payload)
    
    async def _on_price_update(self, event):
        """处理价格更新事件"""
        payload = event.payload
        symbol = payload.get("symbol")
        current_price = payload.get("price")
        
        # 更新所有相关持仓的当前价格
        for order_id, position in self.positions.items():
            if position["symbol"] == symbol:
                position["current_price"] = current_price
                
                # 计算盈亏
                entry_price = position["entry_price"]
                quantity = position["quantity"]
                action = position["action"]
                
                if action == "buy":
                    pnl = (current_price - entry_price) * quantity
                    pnl_percentage = (current_price - entry_price) / entry_price
                else:  # sell/short
                    pnl = (entry_price - current_price) * quantity
                    pnl_percentage = (entry_price - current_price) / entry_price
                
                position["pnl"] = pnl
                position["pnl_percentage"] = pnl_percentage
    
    async def _monitor_position(self, order_id: str):
        """监控单个持仓"""
        try:
            check_interval = self.config.position_check_interval
            
            while self.is_running and order_id in self.positions:
                position = self.positions[order_id]
                pnl_percentage = position["pnl_percentage"]
                
                # 检查止损
                if pnl_percentage <= -self.config.stop_loss_threshold:
                    await self._trigger_stop_loss(order_id, position)
                    break
                
                # 检查止盈
                elif pnl_percentage >= self.config.stop_profit_threshold:
                    await self._trigger_stop_profit(order_id, position)
                    break
                
                # 检查警告线
                elif pnl_percentage <= -0.15:
                    await self._send_warning(order_id, position)
                
                await asyncio.sleep(check_interval)
                
        except asyncio.CancelledError:
            logger.info("position_monitoring_cancelled", order_id=order_id)
        except Exception as e:
            logger.error("position_monitoring_error", order_id=order_id, error=str(e))
    
    async def _trigger_stop_loss(self, order_id: str, position: Dict[str, Any]):
        """触发止损"""
        logger.warning(
            "stop_loss_triggered",
            order_id=order_id,
            symbol=position["symbol"],
            pnl_percentage=position["pnl_percentage"],
            threshold=self.config.stop_loss_threshold
        )
        
        if self.event_bus and self.config.force_close_enabled:
            await self.event_bus.publish("execution.force_close", {
                "order_id": order_id,
                "reason": f"触发止损线 ({abs(position['pnl_percentage'])*100:.1f}% > {self.config.stop_loss_threshold*100:.0f}%)",
                "current_price": position["current_price"],
                "entry_price": position["entry_price"],
                "quantity": position["quantity"],
                "pnl": position["pnl"],
                "pnl_percentage": position["pnl_percentage"]
            })
        
        # 移除持仓
        del self.positions[order_id]
        if order_id in self.monitoring_tasks:
            del self.monitoring_tasks[order_id]
    
    async def _trigger_stop_profit(self, order_id: str, position: Dict[str, Any]):
        """触发止盈"""
        logger.info(
            "stop_profit_triggered",
            order_id=order_id,
            symbol=position["symbol"],
            pnl_percentage=position["pnl_percentage"],
            threshold=self.config.stop_profit_threshold
        )
        
        if self.event_bus:
            await self.event_bus.publish("execution.take_profit", {
                "order_id": order_id,
                "reason": f"触发止盈线 ({position['pnl_percentage']*100:.1f}% > {self.config.stop_profit_threshold*100:.0f}%)",
                "current_price": position["current_price"],
                "entry_price": position["entry_price"],
                "quantity": position["quantity"],
                "pnl": position["pnl"],
                "pnl_percentage": position["pnl_percentage"]
            })
        
        # 移除持仓
        del self.positions[order_id]
        if order_id in self.monitoring_tasks:
            del self.monitoring_tasks[order_id]
    
    async def _send_warning(self, order_id: str, position: Dict[str, Any]):
        """发送警告"""
        logger.warning(
            "risk_warning",
            order_id=order_id,
            symbol=position["symbol"],
            pnl_percentage=position["pnl_percentage"]
        )
        
        if self.event_bus:
            await self.event_bus.publish("notification.send", {
                "type": "risk_warning",
                "title": "风险警告",
                "message": f"持仓{position['symbol']}亏损{abs(position['pnl_percentage'])*100:.1f}%，接近止损线",
                "order_id": order_id,
                "priority": "high"
            })
    
    def get_total_exposure(self) -> float:
        """获取总敞口"""
        total = sum(
            abs(pos["quantity"] * pos["current_price"])
            for pos in self.positions.values()
        )
        return total
    
    def get_daily_pnl(self) -> float:
        """获取当日盈亏"""
        return sum(pos["pnl"] for pos in self.positions.values())
    
    def check_position_limit(self, symbol: str, quantity: float, price: float, capital: float) -> bool:
        """检查仓位限制"""
        position_value = quantity * price
        position_ratio = position_value / capital
        
        if position_ratio > self.config.max_position_size:
            logger.warning(
                "position_limit_exceeded",
                symbol=symbol,
                position_ratio=position_ratio,
                limit=self.config.max_position_size
            )
            return False
        
        return True
    
    def check_exposure_limit(self, additional_exposure: float, capital: float) -> bool:
        """检查总敞口限制"""
        current_exposure = self.get_total_exposure()
        total_exposure = current_exposure + additional_exposure
        exposure_ratio = total_exposure / capital
        
        if exposure_ratio > self.config.max_total_exposure:
            logger.warning(
                "exposure_limit_exceeded",
                exposure_ratio=exposure_ratio,
                limit=self.config.max_total_exposure
            )
            return False
        
        return True

    async def _on_equity_update(self, event):
        """处理权益更新事件"""
        payload = event.payload
        
        # 只处理本账户的权益更新
        if self.account_id and payload.get("account_id") != self.account_id:
            return
        
        self.current_equity = payload.get("equity", 0.0)
        
        # 更新峰值权益
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity
            logger.info("peak_equity_updated", equity=self.peak_equity)
        
        # 如果启用事件驱动模式，在权益更新时立即检查回撤
        if self.config.use_event_driven and self.config.force_close_on_max_drawdown:
            if self.peak_equity > 0 and self.current_equity > 0:
                drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
                
                # 检查是否达到最大回撤
                if drawdown >= self.config.max_drawdown_percent:
                    await self._trigger_max_drawdown_close(drawdown)
                
                # 警告线（最大回撤的80%）
                elif drawdown >= self.config.max_drawdown_percent * 0.8:
                    await self._send_drawdown_warning(drawdown)
    
    async def _monitor_drawdown(self):
        """监控账户回撤"""
        try:
            check_interval = self.config.drawdown_check_interval
            
            # 如果启用事件驱动模式，只在权益更新时检查
            if self.config.use_event_driven:
                logger.info("drawdown_monitoring_event_driven_mode")
                # 事件驱动模式下，检查逻辑在 _on_equity_update 中执行
                while self.is_running:
                    await asyncio.sleep(60)  # 保持任务运行，但不做轮询
                return
            
            # 轮询模式
            logger.info("drawdown_monitoring_polling_mode", interval=check_interval)
            while self.is_running:
                if self.peak_equity > 0 and self.current_equity > 0:
                    # 计算当前回撤
                    drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
                    
                    # 检查是否达到最大回撤
                    if drawdown >= self.config.max_drawdown_percent:
                        await self._trigger_max_drawdown_close(drawdown)
                        break
                    
                    # 警告线（最大回撤的80%）
                    elif drawdown >= self.config.max_drawdown_percent * 0.8:
                        await self._send_drawdown_warning(drawdown)
                
                await asyncio.sleep(check_interval)
                
        except asyncio.CancelledError:
            logger.info("drawdown_monitoring_cancelled")
        except Exception as e:
            logger.error("drawdown_monitoring_error", error=str(e))
    
    async def _trigger_max_drawdown_close(self, drawdown: float):
        """触发最大回撤强制平仓"""
        logger.critical(
            "max_drawdown_triggered",
            account_id=self.account_id,
            drawdown=drawdown,
            threshold=self.config.max_drawdown_percent,
            peak_equity=self.peak_equity,
            current_equity=self.current_equity
        )
        
        if self.event_bus and self.config.force_close_on_max_drawdown:
            # 平仓所有持仓
            for order_id, position in list(self.positions.items()):
                await self.event_bus.publish("execution.force_close", {
                    "order_id": order_id,
                    "reason": f"账户回撤达到{drawdown*100:.1f}%，触发最大回撤强制平仓",
                    "current_price": position["current_price"],
                    "entry_price": position["entry_price"],
                    "quantity": position["quantity"],
                    "pnl": position["pnl"],
                    "pnl_percentage": position["pnl_percentage"],
                    "account_id": self.account_id,
                    "drawdown": drawdown
                })
            
            # 发送紧急通知
            await self.event_bus.publish("notification.send", {
                "type": "max_drawdown_alert",
                "title": "⚠️ 最大回撤强制平仓",
                "message": f"账户回撤达到{drawdown*100:.1f}%，已强制平仓所有持仓",
                "account_id": self.account_id,
                "drawdown": drawdown,
                "peak_equity": self.peak_equity,
                "current_equity": self.current_equity,
                "priority": "critical"
            })
            
            # 暂停交易
            await self.event_bus.publish("trading.suspend", {
                "account_id": self.account_id,
                "reason": "max_drawdown_triggered",
                "drawdown": drawdown
            })
        
        # 清空持仓记录
        self.positions.clear()
        
        # 停止所有监控任务
        for task in self.monitoring_tasks.values():
            task.cancel()
        self.monitoring_tasks.clear()
    
    async def _send_drawdown_warning(self, drawdown: float):
        """发送回撤警告"""
        logger.warning(
            "drawdown_warning",
            account_id=self.account_id,
            drawdown=drawdown,
            threshold=self.config.max_drawdown_percent
        )
        
        if self.event_bus:
            await self.event_bus.publish("notification.send", {
                "type": "drawdown_warning",
                "title": "回撤警告",
                "message": f"账户回撤已达{drawdown*100:.1f}%，接近最大回撤线{self.config.max_drawdown_percent*100:.0f}%",
                "account_id": self.account_id,
                "drawdown": drawdown,
                "priority": "high"
            })
    
    def get_current_drawdown(self) -> float:
        """获取当前回撤百分比"""
        if self.peak_equity <= 0:
            return 0.0
        
        return (self.peak_equity - self.current_equity) / self.peak_equity
    
    def update_equity(self, equity: float):
        """更新账户权益"""
        self.current_equity = equity
        
        if equity > self.peak_equity:
            self.peak_equity = equity
