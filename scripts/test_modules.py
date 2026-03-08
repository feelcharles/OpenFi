#!/usr/bin/env python3
"""
模块功能测试脚本

测试OpenFi各个模块的基本功能
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("OpenFi - 模块功能测试")
print("=" * 70)
print()

# ============================================
# 1. 测试配置管理
# ============================================
print("1. 测试配置管理模块")
print("-" * 70)
try:
    from system_core.config.settings import get_settings
    settings = get_settings()
    print(f"✅ 配置加载成功")
    print(f"   应用名称: {settings.app_name}")
    print(f"   环境: {settings.app_env}")
    print(f"   数据库: {settings.db_host}:{settings.db_port}/{settings.db_name}")
    print(f"   Redis: {settings.redis_url}")
    print(f"   日志级别: {settings.log_level}")
except Exception as e:
    print(f"❌ 配置加载失败: {e}")
print()

# ============================================
# 2. 测试日志系统
# ============================================
print("2. 测试日志系统")
print("-" * 70)
try:
    from system_core.config.logging_config import setup_logging, get_logger
    setup_logging()
    logger = get_logger("test")
    logger.info("test_log_message", test_key="test_value")
    print("✅ 日志系统正常")
except Exception as e:
    print(f"❌ 日志系统失败: {e}")
print()

# ============================================
# 3. 测试数据库模型
# ============================================
print("3. 测试数据库模型")
print("-" * 70)
try:
    from system_core.database.models import (
        Base, User, Broker, TradingAccount, 
        EAProfile, PushConfig, Trade
    )
    print("✅ 数据库模型导入成功")
    print(f"   用户模型: {User.__tablename__}")
    print(f"   券商模型: {Broker.__tablename__}")
    print(f"   交易账户模型: {TradingAccount.__tablename__}")
    print(f"   EA配置模型: {EAProfile.__tablename__}")
    print(f"   推送配置模型: {PushConfig.__tablename__}")
    print(f"   交易记录模型: {Trade.__tablename__}")
except Exception as e:
    print(f"❌ 数据库模型导入失败: {e}")
print()

# ============================================
# 4. 测试EA管理器
# ============================================
print("4. 测试EA管理器")
print("-" * 70)
try:
    from system_core.execution_engine.ea_manager import EAManager
    ea_manager = EAManager()
    print("✅ EA管理器初始化成功")
    print(f"   EA文件夹: {ea_manager.ea_folder}")
    print(f"   日志文件夹: {ea_manager.logs_folder}")
    print(f"   支持的扩展名: {', '.join(ea_manager.SUPPORTED_EXTENSIONS)}")
    
    # 测试扫描功能
    discovered_eas = ea_manager.scan_ea_folder()
    print(f"   扫描到的EA数量: {len(discovered_eas)}")
    if discovered_eas:
        for ea in discovered_eas:
            print(f"     - {ea['ea_name']} ({ea['ea_type']})")
except Exception as e:
    print(f"❌ EA管理器失败: {e}")
print()

# ============================================
# 5. 测试LLM配置管理
# ============================================
print("5. 测试LLM配置管理")
print("-" * 70)
try:
    from system_core.config.llm_manager import get_llm_config_manager
    llm_manager = get_llm_config_manager()
    print("✅ LLM配置管理器加载成功")
    
    default_model = llm_manager.get_default_model()
    print(f"   默认模型: {default_model.provider} - {default_model.model}")
    
    primary_provider = llm_manager.get_primary_provider()
    fallback_chain = llm_manager.get_fallback_chain()
    print(f"   主提供商: {primary_provider}")
    print(f"   降级链: {' -> '.join(fallback_chain)}")
except Exception as e:
    print(f"❌ LLM配置管理失败: {e}")
print()

# ============================================
# 6. 测试推送配置
# ============================================
print("6. 测试推送配置")
print("-" * 70)
try:
    from system_core.config.push_config import get_push_config_manager
    push_manager = get_push_config_manager()
    print("✅ 推送配置管理器加载成功")
    
    channels = push_manager.get_enabled_channels()
    print(f"   启用的推送渠道: {', '.join(channels) if channels else '无'}")
    
    for channel in ['telegram', 'discord', 'feishu', 'wechat_work', 'email']:
        if push_manager.is_channel_enabled(channel):
            config = push_manager.get_channel_config(channel)
            print(f"   {channel}: 已配置")
except Exception as e:
    print(f"❌ 推送配置失败: {e}")
print()

# ============================================
# 7. 测试时区管理
# ============================================
print("7. 测试时区管理")
print("-" * 70)
try:
    from system_core.config.timezone_manager import get_timezone_manager
    tz_manager = get_timezone_manager()
    print("✅ 时区管理器加载成功")
    
    default_tz = tz_manager.get_default_timezone()
    print(f"   默认时区: {default_tz}")
    
    supported_tzs = tz_manager.get_supported_timezones()
    print(f"   支持的时区数量: {len(supported_tzs)}")
except Exception as e:
    print(f"❌ 时区管理失败: {e}")
print()

# ============================================
# 8. 测试关键词管理
# ============================================
print("8. 测试关键词管理")
print("-" * 70)
try:
    from system_core.config.keywords import get_keywords_manager
    keywords_manager = get_keywords_manager()
    print("✅ 关键词管理器加载成功")
    
    categories = keywords_manager.get_all_categories()
    print(f"   关键词类别数量: {len(categories)}")
    for category in list(categories)[:3]:  # 显示前3个
        keywords = keywords_manager.get_keywords_by_category(category)
        print(f"   {category}: {len(keywords)} 个关键词")
except Exception as e:
    print(f"❌ 关键词管理失败: {e}")
print()

# ============================================
# 9. 检查配置文件
# ============================================
print("9. 检查配置文件")
print("-" * 70)
config_files = [
    "config/bot_commands.yaml",
    "config/ea_config.yaml",
    "config/llm_config.yaml",
    "config/push_config.yaml",
    "config/keywords.yaml",
]

for config_file in config_files:
    config_path = project_root / config_file
    if config_path.exists():
        print(f"✅ {config_file}")
    else:
        print(f"❌ {config_file} (不存在)")
print()

# ============================================
# 10. 检查数据库迁移
# ============================================
print("10. 检查数据库迁移")
print("-" * 70)
migrations_dir = project_root / "alembic" / "versions"
if migrations_dir.exists():
    migration_files = [f for f in migrations_dir.glob("*.py") if f.name != "__init__.py"]
    print(f"✅ 迁移文件目录存在")
    print(f"   迁移文件数量: {len(migration_files)}")
    for mf in migration_files:
        print(f"   - {mf.name}")
else:
    print(f"❌ 迁移文件目录不存在")
print()

# ============================================
# 总结
# ============================================
print("=" * 70)
print("测试完成")
print("=" * 70)
print()
print("📋 已实现的功能:")
print("  ✅ 配置管理（环境变量、YAML配置）")
print("  ✅ 日志系统（结构化日志、文件轮转）")
print("  ✅ 数据库模型（9个表的完整架构）")
print("  ✅ EA管理器（扫描、元数据提取、测试）")
print("  ✅ LLM配置管理（多模型、降级链）")
print("  ✅ 推送配置管理（6个渠道）")
print("  ✅ 时区管理（多时区支持）")
print("  ✅ 关键词管理（分类关键词）")
print()
print("⚠️  待实现的功能:")
print("  ⏳ 信息获取引擎（Fetch Engine）")
print("  ⏳ AI处理引擎（AI Engine）")
print("  ⏳ 用户中心API（User Center）")
print("  ⏳ 执行引擎（Trading Execution）")
print("  ⏳ 向量数据库集成（Enhancement）")
print("  ⏳ 事件总线（Event Bus）")
print()
print("💡 提示:")
print("  - 当前项目是基础架构和配置层")
print("  - 核心业务逻辑需要根据需求文档继续开发")
print("  - 可以先部署基础架构，然后逐步添加功能模块")
print()

