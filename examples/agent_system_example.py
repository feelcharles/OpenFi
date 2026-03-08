"""
Agent System Example
智能体系统示例

Demonstrates how to use the multi-agent system:
演示如何使用多智能体系统：
1. Create and configure agents | 创建和配置智能体
2. Start/stop/pause agents | 启动/停止/暂停智能体
3. Monitor agent status | 监控智能体状态
4. Agent isolation | 智能体隔离
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from system_core.agent_system.manager import AgentManager
from system_core.agent_system.models import AgentState

async def example_create_agent():
    """Example: Create a new agent"""
    print("=" * 60)
    print("Example 1: Create Agent | 创建智能体")
    print("=" * 60)
    
    manager = AgentManager()
    
    # Agent configuration
    agent_config = {
        "name": "Momentum Trader",
        "user_id": "user_001",
        "strategy": "momentum",
        "symbols": ["AAPL", "GOOGL", "MSFT"],
        "capital": 10000,
        "risk_level": "medium",
        "max_positions": 3,
        "max_position_size": 0.1
    }
    
    # Create agent
    agent_id = await manager.create_agent(agent_config)
    print(f"\n✅ Agent created successfully!")
    print(f"   Agent ID: {agent_id}")
    print(f"   Name: {agent_config['name']}")
    print(f"   Strategy: {agent_config['strategy']}")
    print(f"   Symbols: {', '.join(agent_config['symbols'])}")
    
    return agent_id

async def example_start_agent(agent_id: str):
    """Example: Start an agent"""
    print("\n" + "=" * 60)
    print("Example 2: Start Agent | 启动智能体")
    print("=" * 60)
    
    manager = AgentManager()
    
    # Start agent
    await manager.start_agent(agent_id)
    print(f"\n✅ Agent started successfully!")
    print(f"   Agent ID: {agent_id}")
    print(f"   State: RUNNING")

async def example_get_agent_status(agent_id: str):
    """Example: Get agent status"""
    print("\n" + "=" * 60)
    print("Example 3: Get Agent Status | 获取智能体状态")
    print("=" * 60)
    
    manager = AgentManager()
    
    # Get status
    status = await manager.get_agent_status(agent_id)
    
    print(f"\n📊 Agent Status:")
    print(f"   State: {status['state']}")
    print(f"   P&L: ${status.get('pnl', 0):.2f}")
    print(f"   Active Positions: {status.get('active_positions', 0)}")
    print(f"   Total Trades: {status.get('total_trades', 0)}")
    print(f"   Win Rate: {status.get('win_rate', 0):.1f}%")

async def example_pause_agent(agent_id: str):
    """Example: Pause an agent"""
    print("\n" + "=" * 60)
    print("Example 4: Pause Agent | 暂停智能体")
    print("=" * 60)
    
    manager = AgentManager()
    
    # Pause agent
    await manager.pause_agent(agent_id)
    print(f"\n⏸️  Agent paused successfully!")
    print(f"   Agent ID: {agent_id}")
    print(f"   State: PAUSED")

async def example_resume_agent(agent_id: str):
    """Example: Resume an agent"""
    print("\n" + "=" * 60)
    print("Example 5: Resume Agent | 恢复智能体")
    print("=" * 60)
    
    manager = AgentManager()
    
    # Resume agent
    await manager.resume_agent(agent_id)
    print(f"\n▶️  Agent resumed successfully!")
    print(f"   Agent ID: {agent_id}")
    print(f"   State: RUNNING")

async def example_update_agent_config(agent_id: str):
    """Example: Update agent configuration"""
    print("\n" + "=" * 60)
    print("Example 6: Update Agent Config | 更新智能体配置")
    print("=" * 60)
    
    manager = AgentManager()
    
    # New configuration
    new_config = {
        "symbols": ["AAPL", "GOOGL", "MSFT", "TSLA"],
        "capital": 15000,
        "risk_level": "high"
    }
    
    # Update configuration
    version = await manager.update_agent_config(agent_id, new_config)
    print(f"\n✅ Configuration updated successfully!")
    print(f"   Agent ID: {agent_id}")
    print(f"   New Version: {version}")
    print(f"   New Symbols: {', '.join(new_config['symbols'])}")
    print(f"   New Capital: ${new_config['capital']}")

async def example_list_agents():
    """Example: List all agents"""
    print("\n" + "=" * 60)
    print("Example 7: List All Agents | 列出所有智能体")
    print("=" * 60)
    
    manager = AgentManager()
    
    # List agents
    agents = await manager.list_agents(user_id="user_001")
    
    print(f"\n📋 Total Agents: {len(agents)}")
    for i, agent in enumerate(agents, 1):
        print(f"\n   {i}. {agent['name']}")
        print(f"      ID: {agent['id']}")
        print(f"      State: {agent['state']}")
        print(f"      Strategy: {agent['strategy']}")

async def example_stop_agent(agent_id: str):
    """Example: Stop an agent"""
    print("\n" + "=" * 60)
    print("Example 8: Stop Agent | 停止智能体")
    print("=" * 60)
    
    manager = AgentManager()
    
    # Stop agent
    await manager.stop_agent(agent_id)
    print(f"\n⏹️  Agent stopped successfully!")
    print(f"   Agent ID: {agent_id}")
    print(f"   State: STOPPED")

async def example_delete_agent(agent_id: str):
    """Example: Delete an agent"""
    print("\n" + "=" * 60)
    print("Example 9: Delete Agent | 删除智能体")
    print("=" * 60)
    
    manager = AgentManager()
    
    # Delete agent
    await manager.delete_agent(agent_id)
    print(f"\n🗑️  Agent deleted successfully!")
    print(f"   Agent ID: {agent_id}")

async def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("AGENT SYSTEM EXAMPLES")
    print("智能体系统示例")
    print("=" * 60)
    
    try:
        # Create agent
        agent_id = await example_create_agent()
        await asyncio.sleep(1)
        
        # Start agent
        await example_start_agent(agent_id)
        await asyncio.sleep(1)
        
        # Get status
        await example_get_agent_status(agent_id)
        await asyncio.sleep(1)
        
        # Pause agent
        await example_pause_agent(agent_id)
        await asyncio.sleep(1)
        
        # Resume agent
        await example_resume_agent(agent_id)
        await asyncio.sleep(1)
        
        # Update configuration
        await example_update_agent_config(agent_id)
        await asyncio.sleep(1)
        
        # List all agents
        await example_list_agents()
        await asyncio.sleep(1)
        
        # Stop agent
        await example_stop_agent(agent_id)
        await asyncio.sleep(1)
        
        # Delete agent
        await example_delete_agent(agent_id)
        
        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("✅ 所有示例成功完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
