# HyperBrain Examples
# HyperBrain 示例代码

**Version**: 1.0  
**Last Updated**: 2026-03-07

---

## Overview | 概述

This directory contains example scripts demonstrating key features of HyperBrain.

本目录包含演示 HyperBrain 关键功能的示例脚本。

---

## Core Examples | 核心示例

### 1. LLM Manager | LLM 管理器

**File**: `llm_manager_example.py`

**Demonstrates | 演示**:
- List available LLM models | 列出可用的 LLM 模型
- Switch between models | 在模型之间切换
- Enable auto mode | 启用自动模式
- Select model for specific tasks | 为特定任务选择模型

**Usage | 使用**:
```bash
python examples/llm_manager_example.py
```

### 2. Factor Screening | 因子筛选

**File**: `factor_screening_example.py`

**Demonstrates | 演示**:
- Single factor screening | 单因子筛选
- Multi-factor screening | 多因子筛选
- Normalization methods | 标准化方法
- Industry neutral screening | 行业中性筛选

**Usage | 使用**:
```bash
python examples/factor_screening_example.py
```

### 3. Agent System | 智能体系统

**File**: `agent_system_example.py`

**Demonstrates | 演示**:
- Create and configure agents | 创建和配置智能体
- Start/stop/pause agents | 启动/停止/暂停智能体
- Monitor agent status | 监控智能体状态
- Agent isolation | 智能体隔离

**Usage | 使用**:
```bash
python examples/agent_system_example.py
```

### 4. Complete Workflow | 完整工作流

**File**: `complete_workflow_example.py`

**Demonstrates | 演示**:
- End-to-end trading workflow | 端到端交易工作流
- Data fetching → Factor analysis → Signal generation → Execution | 数据获取 → 因子分析 → 信号生成 → 执行
- Integration of all major components | 所有主要组件的集成

**Usage | 使用**:
```bash
python examples/complete_workflow_example.py
```

---

## Running Examples | 运行示例

### Prerequisites | 前置要求

1. **Install dependencies | 安装依赖**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment | 配置环境**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start services | 启动服务**:
   ```bash
   docker-compose up -d
   ```

### Run Individual Examples | 运行单个示例

```bash
# LLM Manager example
python examples/llm_manager_example.py

# Factor Screening example
python examples/factor_screening_example.py

# Agent System example
python examples/agent_system_example.py

# Complete Workflow example
python examples/complete_workflow_example.py
```

---

## Example Categories | 示例分类

### Configuration | 配置
- `llm_manager_example.py` - LLM configuration and switching

### Trading | 交易
- `factor_screening_example.py` - Factor-based stock screening
- `agent_system_example.py` - Multi-agent trading system

### Integration | 集成
- `complete_workflow_example.py` - Full system integration

---

## Additional Resources | 其他资源

### Documentation | 文档
- **Trading Features**: [../docs/Trading_Features_Guide.md](../docs/Trading_Features_Guide.md)
- **AI & Agents**: [../docs/AI_Agent_Guide.md](../docs/AI_Agent_Guide.md)
- **System Admin**: [../docs/System_Administration_Guide.md](../docs/System_Administration_Guide.md)

### Configuration Files | 配置文件
- `config/llm_config.yaml` - LLM configuration
- `config/factor_config.yaml` - Factor system configuration
- `config/agent_system_config.yaml` - Agent system configuration

---

## Troubleshooting | 故障排除

### Common Issues | 常见问题

**Issue**: Import errors | 导入错误
```bash
# Solution: Install dependencies
pip install -r requirements.txt
```

**Issue**: Database connection error | 数据库连接错误
```bash
# Solution: Start PostgreSQL
docker-compose up -d db
```

**Issue**: Redis connection error | Redis 连接错误
```bash
# Solution: Start Redis
docker-compose up -d redis
```

**Issue**: API key error | API 密钥错误
```bash
# Solution: Set API keys in .env
echo "OPENAI_API_KEY=your_key_here" >> .env
```

---

## Contributing | 贡献

To add new examples:

1. Create a new Python file in `examples/`
2. Follow the existing example structure
3. Add documentation to this README
4. Test the example thoroughly

添加新示例：

1. 在 `examples/` 中创建新的 Python 文件
2. 遵循现有示例结构
3. 在此 README 中添加文档
4. 彻底测试示例

---

**Document Version**: 1.0  
**Last Review**: 2026-03-07
