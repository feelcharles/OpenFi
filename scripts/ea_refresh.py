#!/usr/bin/env python3
"""
EA Refresh CLI Tool

Usage:
    python scripts/ea_refresh.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from system_core.execution_engine.ea_manager import EAManager

def main():
    """Main entry point for EA refresh tool."""
    print("🔄 开始扫描EA文件夹...")
    print()
    
    try:
        # Initialize EA Manager
        ea_manager = EAManager()
        
        # Refresh EA list
        result = ea_manager.refresh_ea_list()
        
        if result['success']:
            print("✅ EA列表刷新完成")
            print()
            print("📊 统计信息:")
            print(f"  • 总计: {result['total_eas']} 个EA")
            print(f"  • 新增: {result['added']} 个")
            print(f"  • 更新: {result['updated']} 个")
            print(f"  • 移除: {result['removed']} 个")
            print()
            print("🤖 平台分布:")
            print(f"  • MT4: {result['platform_stats']['mt4']} 个")
            print(f"  • MT5: {result['platform_stats']['mt5']} 个")
            print(f"  • TradingView: {result['platform_stats']['tradingview']} 个")
            print()
            print(f"⏰ {result['timestamp']}")
            
            return 0
        else:
            print(f"❌ EA列表刷新失败: {result.get('error', 'Unknown error')}")
            return 1
            
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
