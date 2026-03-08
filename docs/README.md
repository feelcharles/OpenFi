# HyperBrain Documentation
# HyperBrain 文档中心

**Version**: 1.0  
**Last Updated**: 2026-03-07

---

## Documentation Structure | 文档结构

This documentation is organized into three main guides:

本文档分为三个主要指南：

### 1. [Trading Features Guide](Trading_Features_Guide.md) | 交易功能指南

Comprehensive guide for trading-related features:
- Market Data & Screening (市场数据与筛选)
- Factor System (因子系统)
- EA Execution Engine (EA 执行引擎)
- Backtesting (回测系统)
- Research Reports (研报生成)
- Push Notification System (推送通知系统)

### 2. [AI & Agent System Guide](AI_Agent_Guide.md) | AI 与智能体系统指南

Guide for AI and multi-agent system:
- LLM Integration (LLM 集成)
- Multi-Agent System (多智能体系统)
- Agent Configuration (智能体配置)
- Agent Isolation (智能体隔离)
- Prompt Management (提示词管理)

### 3. [System Administration Guide](System_Administration_Guide.md) | 系统管理指南

Guide for system setup and administration:
- System Setup (系统设置)
- Web Backend (Web 后端)
- Security (安全)
- Database Management (数据库管理)
- Monitoring & Logging (监控与日志)
- Backup & Recovery (备份与恢复)
- Configuration Management (配置管理)

---

## Quick Links | 快速链接

### Getting Started | 快速开始

1. **Installation**: See [System Administration Guide - System Setup](System_Administration_Guide.md#system-setup)
2. **First Agent**: See [AI & Agent System Guide - Multi-Agent System](AI_Agent_Guide.md#multi-agent-system)
3. **First Trade**: See [Trading Features Guide - EA Execution Engine](Trading_Features_Guide.md#ea-execution-engine)

### Common Tasks | 常见任务

- **Configure LLM**: [AI & Agent System Guide - LLM Integration](AI_Agent_Guide.md#llm-integration)
- **Setup Notifications**: [Trading Features Guide - Push Notification System](Trading_Features_Guide.md#push-notification-system)
- **Backtest Strategy**: [Trading Features Guide - Backtesting](Trading_Features_Guide.md#backtesting)
- **Manage Security**: [System Administration Guide - Security](System_Administration_Guide.md#security)

### Troubleshooting | 故障排除

Each guide includes a troubleshooting section:
- [Trading Features - Troubleshooting](Trading_Features_Guide.md#troubleshooting)
- [AI & Agent System - Troubleshooting](AI_Agent_Guide.md#troubleshooting)
- [System Administration - Troubleshooting](System_Administration_Guide.md#troubleshooting)

---

## Additional Resources | 其他资源

### Project Documentation | 项目文档

- **Requirements**: `.kiro/specs/openfi/requirements.md`
- **Design**: `.kiro/specs/openfi/design.md`
- **Tasks**: `.kiro/specs/openfi/tasks.md`
- **README**: `../README.md`
- **Quick Start**: `../QUICKSTART.md`

### API Documentation | API 文档

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Configuration Files | 配置文件

All configuration files are in `../config/` directory:
- `agent_system_config.yaml` - Agent system configuration
- `ea_config.yaml` - EA execution configuration
- `factor_config.yaml` - Factor system configuration
- `fetch_sources.yaml` - Data source configuration
- `llm_config.yaml` - LLM provider configuration
- `push_config.yaml` - Notification configuration
- `security_config.yaml` - Security configuration

---

## Documentation Conventions | 文档约定

### Language | 语言

- **Primary Language**: English
- **Secondary Language**: Chinese (中文注释)
- All documents are bilingual with English as the primary language

- **主要语言**: 英文
- **次要语言**: 中文（注释）
- 所有文档均为双语，以英文为主

### Code Examples | 代码示例

All code examples are tested and ready to use:

```python
# Example code is production-ready
from system_core.agent_system.manager import AgentManager

manager = AgentManager()
agent_id = await manager.create_agent(config)
```

### Configuration Examples | 配置示例

Configuration examples use YAML format:

```yaml
# Configuration examples are complete and valid
agents:
  default_config:
    max_positions: 5
    max_daily_loss: 1000
```

---

## Contributing | 贡献

To contribute to documentation:

1. Follow the existing structure
2. Use bilingual format (English + Chinese)
3. Include code examples
4. Test all examples before submitting
5. Update this README if adding new documents

---

## Support | 支持

For questions or issues:

- **GitHub Issues**: https://github.com/feelcharles/OpenFi/issues
- **Email**: support@openfi.local
- **Documentation**: This directory

---

**Document Version**: 1.0  
**Last Review**: 2026-03-07  
**Next Review**: 2026-06-07
