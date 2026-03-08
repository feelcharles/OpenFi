#!/usr/bin/env python3
"""
账户最大回撤强制平仓功能演示
Account Max Drawdown Force Close Demo

演示如何使用账户级别的最大回撤强制平仓功能
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from system_core.risk_control import RiskManager
from system_core.event_bus import EventBus
from system_core.config import get_logger

logger = get_logger(__name__)


async def demo_max_drawdown_protection():
    """演示最大回撤保护功能"""
    
    print("="*70)
    print("账户最大回撤强制平仓功能演示")
    print("Account Max Drawdown Force Close Demo")
    print("="*70)
    print()
    
    # 1. 初始化事件总线
    print("1. 初始化事件总线...")
    event_bus = EventBus(redis_url="redis://localhost:6379/0")
    await event_bus.connect()
    print("   ✓ 事件总线已连接\n")
    
    # 2. 创建风险管理器（指定账户ID）
    print("2. 创建风险管理器...")
    risk_manager = RiskManager(
        event_bus=event_bus,
        account_id="mt4_demo_001"
    )
    await risk_manager.initialize()
    print(f"   ✓ 风险管理器已初始化")
    print(f"   - 账户ID: {risk_manager.account_id}")
    print(f"   - 最大回撤阈值: {risk_manager.config.max_drawdown_percent*100:.0f}%")
    print(f"   - 强制平仓: {risk_manager.config.force_close_on_max_drawdown}\n")
    
    # 3. 设置初始权益
    print("3. 设置初始账户权益...")
    initial_equity = 10000.0
    risk_manager.update_equity(initial_equity)
    print(f"   ✓ 初始权益: ${initial_equity:,.2f}")
    print(f"   ✓ 峰值权益: ${risk_manager.peak_equity:,.2f}\n")
    
    # 4. 模拟交易盈利，更新峰值
    print("4. 模拟交易盈利...")
    profit_equity = 12000.0
    risk_manager.update_equity(profit_equity)
    print(f"   ✓ 当前权益: ${profit_equity:,.2f}")
    print(f"   ✓ 峰值权益: ${risk_manager.peak_equity:,.2f}")
    print(f"   ✓ 当前回撤: {risk_manager.get_current_drawdown()*100:.1f}%\n")
    
    # 5. 模拟小幅回撤（10%）
    print("5. 模拟小幅回撤（10%）...")
    equity_10_drawdown = 10800.0
    risk_manager.update_equity(equity_10_drawdown)
    drawdown = risk_manager.get_current_drawdown()
    print(f"   ✓ 当前权益: ${equity_10_drawdown:,.2f}")
    print(f"   ✓ 当前回撤: {drawdown*100:.1f}%")
    print(f"   ✓ 状态: 正常交易\n")
    
    # 6. 模拟中等回撤（16% - 触发警告）
    print("6. 模拟中等回撤（16% - 触发警告）...")
    equity_16_drawdown = 10080.0
    risk_manager.update_equity(equity_16_drawdown)
    drawdown = risk_manager.get_current_drawdown()
    print(f"   ✓ 当前权益: ${equity_16_drawdown:,.2f}")
    print(f"   ✓ 当前回撤: {drawdown*100:.1f}%")
    print(f"   ⚠️  状态: 警告 - 接近最大回撤线\n")
    
    # 7. 模拟严重回撤（20% - 触发强制平仓）
    print("7. 模拟严重回撤（20% - 触发强制平仓）...")
    equity_20_drawdown = 9600.0
    
    # 订阅强制平仓事件
    force_close_triggered = False
    
    async def on_force_close(event):
        nonlocal force_close_triggered
        force_close_triggered = True
        print(f"\n   🚨 强制平仓事件触发!")
        print(f"   - 原因: {event.payload.get('reason')}")
        print(f"   - 回撤: {event.payload.get('drawdown', 0)*100:.1f}%")
        print(f"   - 峰值权益: ${event.payload.get('peak_equity', 0):,.2f}")
        print(f"   - 当前权益: ${event.payload.get('current_equity', 0):,.2f}")
    
    await event_bus.subscribe("execution.force_close", on_force_close)
    
    # 添加一个模拟持仓
    risk_manager.positions["ORDER_001"] = {
        "symbol": "AAPL",
        "action": "buy",
        "quantity": 100,
        "entry_price": 150.0,
        "current_price": 145.0,
        "pnl": -500.0,
        "pnl_percentage": -0.033
    }
    
    risk_manager.update_equity(equity_20_drawdown)
    drawdown = risk_manager.get_current_drawdown()
    print(f"   ✓ 当前权益: ${equity_20_drawdown:,.2f}")
    print(f"   ✓ 当前回撤: {drawdown*100:.1f}%")
    
    # 手动触发强制平仓（因为监控任务是异步的）
    if drawdown >= risk_manager.config.max_drawdown_percent:
        await risk_manager._trigger_max_drawdown_close(drawdown)
    
    # 等待事件处理
    await asyncio.sleep(1)
    
    if force_close_triggered:
        print(f"   ✓ 所有持仓已平仓")
        print(f"   ✓ 账户交易已暂停\n")
    
    # 8. 显示最终统计
    print("8. 最终统计...")
    print(f"   - 峰值权益: ${risk_manager.peak_equity:,.2f}")
    print(f"   - 当前权益: ${risk_manager.current_equity:,.2f}")
    print(f"   - 最大回撤: {risk_manager.get_current_drawdown()*100:.1f}%")
    print(f"   - 持仓数量: {len(risk_manager.positions)}")
    print()
    
    # 9. 清理
    print("9. 清理资源...")
    await event_bus.unsubscribe("execution.force_close", on_force_close)
    await risk_manager.close()
    await event_bus.disconnect()
    print("   ✓ 资源已清理\n")
    
    print("="*70)
    print("演示完成！")
    print("="*70)
    print()
    print("要点总结:")
    print("1. 系统实时监控账户权益和回撤")
    print("2. 回撤达到80%阈值时发送警告")
    print("3. 回撤达到100%阈值时强制平仓所有持仓")
    print("4. 平仓后自动暂停账户交易")
    print("5. 发送高优先级通知给用户")
    print()
    print("Web界面访问: http://localhost:8686/account_settings.html")
    print()


async def demo_api_usage():
    """演示API使用"""
    
    print("="*70)
    print("账户风险设置API使用示例")
    print("="*70)
    print()
    
    print("1. 获取所有账户:")
    print("   curl http://localhost:8686/api/v1/accounts/")
    print()
    
    print("2. 获取指定账户:")
    print("   curl http://localhost:8686/api/v1/accounts/mt4_demo_001")
    print()
    
    print("3. 更新风险设置:")
    print("   curl -X PUT http://localhost:8686/api/v1/accounts/mt4_demo_001/risk-management \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{")
    print("       \"max_daily_loss_percent\": 5.0,")
    print("       \"max_total_risk_percent\": 20.0,")
    print("       \"max_open_positions\": 10,")
    print("       \"max_drawdown_percent\": 20.0,")
    print("       \"force_close_on_max_drawdown\": true")
    print("     }'")
    print()
    
    print("4. 启用账户:")
    print("   curl -X POST http://localhost:8686/api/v1/accounts/mt4_demo_001/enable")
    print()
    
    print("5. 禁用账户:")
    print("   curl -X POST http://localhost:8686/api/v1/accounts/mt4_demo_001/disable")
    print()
    
    print("6. 获取账户状态:")
    print("   curl http://localhost:8686/api/v1/accounts/mt4_demo_001/status")
    print()


async def main():
    """主函数"""
    
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                                                                    ║")
    print("║          账户最大回撤强制平仓功能演示                              ║")
    print("║          Account Max Drawdown Force Close Demo                    ║")
    print("║                                                                    ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print()
    
    try:
        # 演示1: 最大回撤保护
        await demo_max_drawdown_protection()
        
        # 等待用户
        print("\n按Enter键继续查看API使用示例...")
        input()
        
        # 演示2: API使用
        await demo_api_usage()
        
    except KeyboardInterrupt:
        print("\n\n演示被用户中断")
    except Exception as e:
        print(f"\n\n演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
