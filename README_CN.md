# OpenFi - 您的智能交易伙伴

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)](.)

> **穿透信息迷雾的智能情报**  
> **驾驭多维数据的量化引擎**  
> **银行级加密守护的私密空间，赋能你的每一次决策**

**[English](README.md)** | **[中文](README_CN.md)**

---

## 🚀 快速开始

### 一键部署

```bash
curl -fsSL https://raw.githubusercontent.com/feelcharles/OpenFi/main/quick_deploy.sh -o deploy.sh && sudo bash deploy.sh
```

**部署完成后启动服务**:
```bash
systemctl start openfi
```

**部署后访问地址**:
- **主应用**: `http://你的服务器IP:8686/app`
- API 文档: `http://你的服务器IP:8686/docs`
- 健康检查: `http://你的服务器IP:8686/health`

**默认账户**: 
- 用户名: `admin`
- 密码: `admin123`
- ⚠️ **首次登录必须修改密码**

**系统要求**: 
- 操作系统: Ubuntu 20.04+ / CentOS 7+ / Debian 11+
- CPU: 2核以上
- 内存: 2GB 以上
- Python: 3.11+

### 服务器管理

**启动服务器**:
```bash
systemctl start openfi
```

**停止服务器**:
```bash
systemctl stop openfi
```

**重启服务器**:
```bash
systemctl restart openfi
```

**查看服务状态**:
```bash
systemctl status openfi
```

**查看实时日志**:
```bash
journalctl -u openfi -f
```

### 系统重置

⚠️ **危险操作**: 此操作将删除所有数据，包括数据库、配置文件和日志，无法恢复！

```bash
sudo bash /opt/openfi/scripts/reset_system.sh
```

重置过程需要:
1. 输入 `YES` (大写) 进行第一次确认
2. 输入 `RESET` (大写) 进行第二次确认
3. 输入管理员密码进行验证
4. 等待5秒倒计时（可按 Ctrl+C 取消）

重置完成后，可以重新运行一键部署脚本重新安装系统。

---

## 📋 功能特性

### 🎯 情报中心
- **AI 驱动的新闻过滤**: 自动过滤和分析市场新闻
- **多源数据聚合**: 从各种金融数据源收集数据
- **情绪分析**: 实时市场情绪追踪
- **事件检测**: 识别高影响力市场事件

### 📊 行情监控
- **实时数据**: 多资产价格监控
- **自选股管理**: 追踪您关注的股票
- **技术指标**: 内置技术分析工具
- **告警系统**: 可定制的价格和指标告警

### ⚡ 量化引擎
- **因子系统**: 100+ 内置量化因子
- **回测**: 历史策略测试与详细指标
- **因子筛选**: 多因子选股
- **绩效分析**: 全面的绩效报告

### 🤖 AI 代理
- **自主分析**: AI 代理 24/7 分析市场数据
- **交易信号**: 生成高置信度交易信号
- **风险评估**: 自动风险评估
- **报告生成**: 每日和每周市场报告

### 💰 交易管理
- **多平台支持**: MT4、MT5、TradingView
- **EA 管理**: 专家顾问部署和监控
- **持仓追踪**: 实时持仓和盈亏追踪
- **风险控制**: 全面的风险管理系统

### 🔒 安全与隐私
- **银行级加密**: 端到端数据加密
- **JWT 认证**: 安全的基于令牌的认证
- **速率限制**: API 速率限制和 DDoS 防护
- **审计日志**: 所有操作的完整审计跟踪

---

## 🎓 入门指南

### 1. 安装

#### 方案 A: 一键部署（推荐）
```bash
curl -fsSL https://raw.githubusercontent.com/feelcharles/OpenFi/main/quick_deploy.sh -o deploy.sh && sudo bash deploy.sh
```

#### 方案 B: 手动安装
```bash
# 克隆仓库
git clone https://github.com/feelcharles/OpenFi.git
cd OpenFi

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python scripts/db_migrate.py

# 启动服务器
python -m uvicorn system_core.web_backend.app:app --host 0.0.0.0 --port 8686
```

### 2. 首次登录

1. 打开浏览器访问 `http://你的服务器IP:8686/app`
2. 使用默认账户登录: `admin` / `admin123`
3. 根据提示**立即修改密码**
4. 完成初始设置

### 3. 配置

#### API 密钥设置
1. 导航到 **系统** → **配置**
2. 选择 `llm_config.yaml`
3. 添加您的 API 密钥:
   ```yaml
   llm_providers:
     openai:
       api_key: "your-openai-api-key"
       model: "gpt-4"
     anthropic:
       api_key: "your-anthropic-api-key"
       model: "claude-3-opus"
   ```
4. 修改后 **2 秒自动保存**

#### 数据源配置
1. 选择 `fetch_sources.yaml`
2. 配置您的数据源:
   ```yaml
   sources:
     - name: "Alpha Vantage"
       type: "market_data"
       api_key: "your-api-key"
       enabled: true
   ```

#### 推送通知
1. 选择 `push_config.yaml`
2. 配置通知渠道:
   ```yaml
   channels:
     telegram:
       enabled: true
       bot_token: "your-bot-token"
       chat_id: "your-chat-id"
   ```

---

## 📱 Web 界面指南

### 仪表板概览
- **系统状态**: 实时系统健康监控
- **最新信号**: 最新的 AI 生成交易信号
- **市场概览**: 快速市场快照
- **绩效指标**: 投资组合绩效追踪

### 情报模块
- **新闻流**: AI 过滤的新闻及相关性评分
- **事件日历**: 即将到来的市场事件
- **情绪仪表板**: 市场情绪指标
- **研究报告**: AI 生成的市场分析

### 行情模块
- **自选股**: 追踪多个股票代码
- **图表**: 带指标的交互式价格图表
- **报价**: 实时价格报价
- **筛选器**: 股票筛选工具

### 量化引擎
- **因子库**: 浏览和测试因子
- **回测**: 运行历史策略测试
- **筛选**: 多因子选股
- **绩效**: 分析回测结果

### AI 代理
- **代理仪表板**: 监控 AI 代理活动
- **信号历史**: 查看生成的信号
- **代理配置**: 自定义代理行为
- **绩效追踪**: 代理绩效指标

### 交易
- **账户**: 管理交易账户
- **持仓**: 查看持仓
- **订单**: 订单管理
- **历史**: 交易历史和盈亏

### 系统
- **配置**: 编辑系统设置（启用自动保存）
- **用户**: 用户管理
- **日志**: 系统日志和审计跟踪
- **监控**: 系统性能指标

---

## 🤖 AI 代理能力

### 1. 市场分析代理
- **每日市场摘要**: 全面的市场概览
- **板块分析**: 行业特定洞察
- **趋势检测**: 识别市场趋势
- **相关性分析**: 资产相关性追踪

### 2. 新闻分析代理
- **新闻过滤**: 从噪音中过滤相关新闻
- **情绪评分**: 量化新闻情绪
- **影响评估**: 评估新闻对市场的影响
- **事件提取**: 从新闻中提取关键事件

### 3. 交易信号代理
- **信号生成**: 生成交易信号
- **置信度评分**: 分配置信度水平
- **风险评估**: 评估信号风险
- **进出点**: 建议最佳进出点

### 4. 风险管理代理
- **投资组合风险**: 监控投资组合风险指标
- **仓位大小**: 推荐仓位大小
- **止损**: 建议止损水平
- **敞口分析**: 分析市场敞口

### 5. 报告生成代理
- **每日报告**: 自动化每日市场报告
- **每周摘要**: 每周绩效摘要
- **自定义报告**: 生成自定义分析报告
- **绩效归因**: 分析收益来源

---

## 🔧 API 集成

### 认证
```python
import requests

# 登录
response = requests.post(
    "http://localhost:8686/api/v1/auth/login",
    json={"username": "admin", "password": "your-password"}
)
token = response.json()["access_token"]

# 在后续请求中使用令牌
headers = {"Authorization": f"Bearer {token}"}
```

### 获取市场数据
```python
# 获取系统状态
response = requests.get(
    "http://localhost:8686/api/v1/dashboard/system-status",
    headers=headers
)
print(response.json())

# 获取最新信号
response = requests.get(
    "http://localhost:8686/api/v1/dashboard/signals?limit=10",
    headers=headers
)
signals = response.json()
```

### Bot 命令
```python
# 执行 bot 命令
response = requests.post(
    "http://localhost:8686/api/v1/bot/command",
    headers=headers,
    json={"command": "/analyze AAPL"}
)
print(response.json()["response"])
```

### 配置管理
```python
# 获取配置
response = requests.get(
    "http://localhost:8686/api/v1/config/llm_config.yaml",
    headers=headers
)
config = response.json()["content"]

# 更新配置（自动保存）
response = requests.put(
    "http://localhost:8686/api/v1/config/llm_config.yaml",
    headers=headers,
    json={"content": updated_config}
)
```

---

## 🛡️ 实盘交易安全

### 风险控制功能
1. **仓位限制**: 每个股票的最大仓位大小
2. **每日亏损限制**: 达到每日亏损阈值后停止交易
3. **回撤保护**: 回撤时自动停止交易
4. **订单验证**: 交易前风险检查
5. **紧急停止**: 一键紧急停止按钮

### 最佳实践
- ✅ **从小开始**: 从小仓位开始
- ✅ **模拟交易**: 先在模拟中测试策略
- ✅ **设置限制**: 始终设置止损和仓位限制
- ✅ **密切监控**: 在交易时段监控持仓
- ✅ **定期审查**: 审查绩效并调整

### 安全检查清单
- [ ] 配置仓位限制
- [ ] 设置每日亏损限制
- [ ] 在回测中测试策略
- [ ] 验证 API 连接
- [ ] 启用风险告警
- [ ] 审查紧急程序

---

## 📊 量化引擎

### 因子系统
- **技术因子**: 价格、成交量、动量指标
- **基本面因子**: 财务比率、盈利指标
- **情绪因子**: 新闻情绪、社交媒体情绪
- **自定义因子**: 创建您自己的因子

### 回测
```python
# 回测配置示例
backtest_config = {
    "strategy": "momentum",
    "universe": ["AAPL", "GOOGL", "MSFT"],
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "initial_capital": 100000,
    "factors": ["momentum_20", "volume_ratio"],
    "rebalance": "monthly"
}
```

### 绩效指标
- **收益**: 总收益、年化收益、CAGR
- **风险**: 波动率、最大回撤、夏普比率
- **交易**: 胜率、盈亏比、平均交易
- **归因**: 因子贡献分析

---

## 📚 文档

### 核心文档
- [DEPLOYMENT.md](DEPLOYMENT.md) - 详细部署指南
- [API.md](API.md) - 完整 API 参考
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - 快速命令参考

### 技术文档
- [PYTHON_VERSION_UPGRADE.md](PYTHON_VERSION_UPGRADE.md) - Python 3.11+ 升级详情
- [PORT_CONFIGURATION.md](PORT_CONFIGURATION.md) - 端口配置指南
- [LIVE_TRADING_RISK_CONTROL.md](LIVE_TRADING_RISK_CONTROL.md) - 风险控制文档

### 其他资源
- [DOCS_INDEX.md](DOCS_INDEX.md) - 完整文档索引
- [示例](examples/) - 代码示例和教程
- [模拟](simulation/) - 测试和模拟工具

---

## 🧪 测试

### 运行测试
```bash
# 运行所有测试
python run_all_tests.py

# 运行特定测试
python simulation/test_complete_system.py

# 运行 Web UI 测试
python test_web_ui.py
```

### 测试覆盖率
- ✅ 核心模块 (8/8 通过)
- ✅ Web UI (7/7 通过)
- ✅ API 端点 (14/14 通过)
- ✅ 集成测试 (2/2 通过)

---

## 🤝 贡献

欢迎贡献！请随时提交 Pull Request。

### 开发设置
```bash
# 克隆仓库
git clone https://github.com/feelcharles/OpenFi.git
cd OpenFi

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行测试
python run_all_tests.py
```

---

## 📄 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE)

---

## 🙏 致谢

- FastAPI 提供优秀的 Web 框架
- SQLAlchemy 提供数据库 ORM
- OpenAI 和 Anthropic 提供 AI 能力
- 所有贡献者和用户

---

## 📞 支持

- **问题**: [GitHub Issues](https://github.com/feelcharles/OpenFi/issues)
- **文档**: [完整文档](DOCS_INDEX.md)
- **示例**: [代码示例](examples/)

---

## ⚠️ 免责声明

本软件仅用于教育和研究目的。交易涉及风险。过去的表现不能保证未来的结果。在做出投资决策之前，请务必进行自己的研究并咨询财务顾问。

---

**由 OpenFi 团队用 ❤️ 制作**

**版本**: 1.0.0  
**最后更新**: 2026-03-08
