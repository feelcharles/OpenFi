"""
LLM Manager 使用示例

演示如何使用LLM管理器进行模型切换和自动选择
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from system_core.config.llm_manager import get_llm_manager

def main():
    """主函数"""
    print("=" * 60)
    print("LLM Manager 使用示例")
    print("=" * 60)
    
    # 获取LLM管理器
    manager = get_llm_manager()
    
    # 1. 查看所有可用模型
    print("\n1. 查看所有可用模型:")
    print(manager.get_model_list_text())
    
    # 2. 查看当前模型信息
    print("\n2. 当前模型信息:")
    current_info = manager.get_current_model_info()
    print(f"   模型: {current_info['display_name']}")
    print(f"   提供商: {current_info['provider']}")
    print(f"   类型: {current_info['type']}")
    print(f"   上下文窗口: {current_info['context_window']} tokens")
    print(f"   成本: ${current_info['cost_per_1k_tokens']}/1K tokens")
    
    # 3. 切换到指定编号的模型
    print("\n3. 切换到模型编号 2:")
    success, message, old_model = manager.switch_model(2)
    if success:
        print(f"   ✅ {message}")
        print(f"   从: {old_model.display_name}")
        print(f"   到: {manager.current_model.display_name}")
    else:
        print(f"   ❌ {message}")
    
    # 4. 切换到fast模型
    print("\n4. 切换到 fast 模型:")
    success, message, old_model = manager.switch_to_fast()
    if success:
        print(f"   ✅ {message}")
    else:
        print(f"   ❌ {message}")
    
    # 5. 切换到pro模型
    print("\n5. 切换到 pro 模型:")
    success, message, old_model = manager.switch_to_pro()
    if success:
        print(f"   ✅ {message}")
    else:
        print(f"   ❌ {message}")
    
    # 6. 启用自动模式
    print("\n6. 启用自动模式:")
    success, message = manager.enable_auto_mode()
    print(f"   ✅ {message}")
    
    # 7. 自动选择模型（简单任务）
    print("\n7. 自动选择模型（简单任务 - 翻译）:")
    selected_model = manager.select_model_for_task('translation', input_length=100)
    print(f"   选择的模型: {selected_model.display_name} ({selected_model.type})")
    
    # 8. 自动选择模型（复杂任务）
    print("\n8. 自动选择模型（复杂任务 - 分析）:")
    selected_model = manager.select_model_for_task('analysis', input_length=2000)
    print(f"   选择的模型: {selected_model.display_name} ({selected_model.type})")
    
    # 9. 查看fast和pro模型列表
    print("\n9. Fast 模型列表:")
    for model in manager.get_fast_models():
        print(f"   • {model.display_name} ({model.provider})")
    
    print("\n10. Pro 模型列表:")
    for model in manager.get_pro_models():
        print(f"   • {model.display_name} ({model.provider})")
    
    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
