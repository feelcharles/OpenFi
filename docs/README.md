# OpenFi 文档中心
# OpenFi Documentation Center

**Version**: 2.0  
**Last Updated**: 2026-03-09

---

## 主要文档 | Main Documentation

### 📘 [用户指南 (User Guide)](USER_GUIDE.md)

完整的用户使用指南，包含：
- 系统概述和快速开始
- 端到端工作流程详解
- 风险控制配置（支持高频/低频）
- 账户管理和风险参数设置
- 常见问题和最佳实践

**推荐所有用户首先阅读此文档**

---

## 快速链接 | Quick Links

### 核心功能

- **账户设置**：[用户指南 - 账户管理](USER_GUIDE.md#账户管理)
- **风险控制**：[用户指南 - 风险控制配置](USER_GUIDE.md#风险控制配置)
- **工作流程**：[用户指南 - 端到端工作流程](USER_GUIDE.md#端到端工作流程)
- **常见问题**：[用户指南 - 常见问题](USER_GUIDE.md#常见问题)

### Web界面

- **账户设置页面**：http://localhost:8686/account_settings.html
- **API文档**：http://localhost:8686/docs
- **ReDoc**：http://localhost:8686/redoc

### 快速开始

1. **启动系统**：运行 `start.bat` (Windows) 或 `./start.sh` (Linux/Mac)
2. **访问界面**：打开 http://localhost:8686/account_settings.html
3. **配置账户**：设置风险参数并启用账户
4. **开始交易**：系统自动执行工作流程

---

## 系统测试 | System Testing

### 运行测试

```bash
# 运行所有测试
python test_system.py --all

# 运行数据库完整性检查
python test_system.py --db-check

# 详细输出
python test_system.py --all --verbose
```

### 演示脚本

```bash
# 风险控制演示
python examples/account_risk_demo.py

# 完整工作流演示
python examples/complete_workflow_example.py
```

---

## 配置文件 | Configuration Files

所有配置文件位于 `../config/` 目录：

### 核心配置

- `accounts.yaml` - 账户配置（包含风险参数）
- `risk_config.yaml` - 风险控制配置（监控间隔等）
- `ea_config.yaml` - EA执行配置
- `factor_config.yaml` - 因子系统配置

### 其他配置

- `llm_config.yaml` - LLM提供商配置
- `push_config.yaml` - 推送通知配置
- `security_config.yaml` - 安全配置
- `fetch_sources.yaml` - 数据源配置
- `agent_system_config.yaml` - 智能体系统配置

---

## 文档约定 | Documentation Conventions

### 语言 | Language

- **主要语言**：中文
- **次要语言**：英文
- 所有文档均为双语

### 代码示例 | Code Examples

所有代码示例均已测试，可直接使用：

```python
# 示例代码可直接运行
from system_core.risk_control.risk_manager import RiskManager

risk_manager = RiskManager(account_id="mt4_demo_001")
await risk_manager.initialize()
```

### 配置示例 | Configuration Examples

配置示例使用YAML格式：

```yaml
# 配置示例完整且有效
risk_management:
  max_drawdown_percent: 20.0
  force_close_on_max_drawdown: true
```

---

## 其他资源 | Additional Resources

### 项目文档

- **主README**：`../README.md`
- **快速部署**：`../QUICK_DEPLOY.md`
- **部署指南**：`../DEPLOYMENT.md`
- **数据库完整性**：`../DATABASE_INTEGRITY_GUIDE.md`
- **API文档**：`../API.md`

### 在线资源

- **GitHub仓库**：https://github.com/feelcharles/OpenFi
- **问题反馈**：https://github.com/feelcharles/OpenFi/issues

---

## 支持 | Support

如有问题或建议：

- **GitHub Issues**：https://github.com/feelcharles/OpenFi/issues
- **Email**：support@openfi.local
- **文档目录**：本目录

---

**文档版本**：2.0  
**最后审查**：2026-03-09  
**下次审查**：2026-06-09
