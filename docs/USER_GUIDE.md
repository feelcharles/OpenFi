# OpenFi 用户指南
# OpenFi User Guide

**版本**: 2.0  
**最后更新**: 2026-03-09

---

## 目录

1. [系统概述](#系统概述)
2. [快速开始](#快速开始)
3. [端到端工作流程](#端到端工作流程)
4. [风险控制配置](#风险控制配置)
5. [账户管理](#账户管理)
6. [常见问题](#常见问题)

---

## 系统概述

OpenFi是一个智能量化交易系统，集成了AI分析、因子回测、风险控制等功能。

### 核心功能

- 🤖 AI驱动的市场分析
- 📊 多因子量化策略
- 🔄 自动化交易执行
- 🛡️ 智能风险控制
- 📱 多渠道推送通知
- 🎯 高频/低频策略支持

### 系统架构

```
数据获取 → AI分析 → 量化回测 → 报告推送 
    → 用户确认 → 实盘执行 → 风险监控
```

---

## 快速开始

### 1. 启动系统

```bash
# Windows
start.bat

# Linux/Mac
./start.sh
```

### 2. 访问Web界面

```
http://localhost:8686/account_settings.html
```

### 3. 配置账户

1. 选择要配置的账户
2. 设置风险参数
3. 点击"保存设置"
4. 点击"启用"激活账户

---

## 端到端工作流程

### 完整流程图

```
┌─────────────────┐
│  1. 信息获取     │  从多个数据源获取市场数据
│  Data Fetch     │  (价格、新闻、社交媒体、技术指标)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. AI分析      │  使用LLM分析市场情绪和趋势
│  AI Analysis    │  (情绪、置信度、关键因素、建议)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. 量化回测     │  运行Factor和EA策略回测
│  Backtest       │  (夏普比率、回撤、胜率、收益)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. 报告推送     │  生成并推送分析报告
│  Report Push    │  (Telegram、Email、Web)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. 用户命令     │  用户通过Bot发送执行命令
│  User Command   │  (确认执行、修改参数、取消)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  6. 实盘执行     │  AI执行Factor和EA策略
│  Live Execution │  (下单、持仓管理)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  7. 风险控制     │  实时监控，自动止损止盈
│  Risk Control   │  (止损、止盈、回撤监控)
└─────────────────┘
```

### 各步骤详解

#### 1. 信息获取

系统自动从多个数据源获取：
- 实时行情数据
- 财经新闻资讯
- 社交媒体情绪
- 技术指标数据

#### 2. AI分析

LLM分析市场数据，生成：
- 市场情绪评估（看涨/看跌/中性）
- 置信度评分（0-1）
- 关键影响因素
- 交易建议和目标价格

#### 3. 量化回测

对策略进行历史回测：
- 计算夏普比率
- 评估最大回撤
- 统计胜率
- 计算总收益

#### 4. 报告推送

通过多渠道推送分析报告：
- Telegram Bot通知
- Email邮件
- Web界面通知
- 移动App推送

#### 5. 用户命令

用户通过Bot发送命令：
- `/execute` - 执行交易
- `/modify` - 修改参数
- `/cancel` - 取消操作
- `/status` - 查看状态

#### 6. 实盘执行

系统执行交易：
- 验证用户权限
- 检查账户余额
- 计算仓位大小
- 下单并记录

#### 7. 风险控制

实时监控并自动处理：
- 止损触发（默认20%）
- 止盈触发（默认30%）
- 回撤监控
- 强制平仓

---

## 风险控制配置

### 监控间隔设置

系统支持从低频到高频的不同交易场景。

#### 标准模式（默认）

适用于日内交易、波段交易。

```yaml
# config/risk_config.yaml
risk_control:
  monitoring:
    position_check_interval: 5  # 持仓检查间隔（秒）
    drawdown_check_interval: 1  # 回撤检查间隔（秒）
```

#### 高频模式

适用于高频量化、算法交易。

```yaml
risk_control:
  high_frequency_mode:
    enabled: true
    position_check_interval: 0.1  # 100毫秒
    drawdown_check_interval: 0.1  # 100毫秒
    use_event_driven: true  # 事件驱动，零延迟
```

### 配置建议

| 交易类型 | 持仓检查 | 回撤检查 | 事件驱动 |
|---------|---------|---------|---------|
| 日内交易 | 5-10秒 | 1-5秒 | 否 |
| 分钟级策略 | 1-5秒 | 0.5-1秒 | 否 |
| 秒级策略 | 0.5-1秒 | 0.1-0.5秒 | 是 |
| 高频交易 | 0.1-0.5秒 | 0.1秒 | 是 |
| 超高频 | 0.05-0.1秒 | 0.05-0.1秒 | 是 |

### 轮询 vs 事件驱动

**轮询模式**：
- 按固定间隔检查
- 简单可靠
- 适合低频交易

**事件驱动模式**：
- 权益更新时立即检查
- 零延迟响应
- 适合高频交易
- 资源消耗更低

### 配置示例

#### 场景1：日内交易

```yaml
risk_control:
  monitoring:
    position_check_interval: 10
    drawdown_check_interval: 5
  high_frequency_mode:
    enabled: false
```

#### 场景2：高频量化

```yaml
risk_control:
  high_frequency_mode:
    enabled: true
    position_check_interval: 0.1
    drawdown_check_interval: 0.1
    use_event_driven: true
```

---

## 账户管理

### 访问账户设置

**Web界面**：
```
http://localhost:8686/account_settings.html
```

**API接口**：
```bash
# 获取所有账户
curl http://localhost:8686/api/v1/accounts/

# 获取特定账户
curl http://localhost:8686/api/v1/accounts/mt4_demo_001
```

### 风险参数说明

#### 1. 每日最大亏损 (Max Daily Loss)

**参数**: `max_daily_loss_percent`  
**范围**: 0% - 100%  
**默认值**: 5%

当日累计亏损达到此百分比时，系统暂停当日交易。

**示例**：
- 账户余额：$10,000
- 设置：5%
- 触发条件：当日亏损 ≥ $500

#### 2. 总风险百分比 (Max Total Risk)

**参数**: `max_total_risk_percent`  
**范围**: 0% - 100%  
**默认值**: 20%

所有持仓的总风险敞口不能超过此百分比。

#### 3. 最大持仓数 (Max Open Positions)

**参数**: `max_open_positions`  
**范围**: 1 - 无限制  
**默认值**: 10

同时持有的最大仓位数量。

#### 4. 最大回撤强制平仓 ⚠️

**参数**: `max_drawdown_percent`  
**范围**: 0% - 100%  
**默认值**: 20%

**这是最重要的风险控制参数！**

当账户回撤达到此百分比时，系统将：
1. 立即强制平仓所有持仓
2. 发送紧急通知
3. 暂停账户交易

**回撤计算公式**：
```
回撤 = (峰值权益 - 当前权益) / 峰值权益 × 100%
```

**示例**：
- 峰值权益：$12,000
- 当前权益：$9,600
- 回撤：(12,000 - 9,600) / 12,000 = 20%
- 结果：触发强制平仓

#### 5. 强制平仓开关

**参数**: `force_close_on_max_drawdown`  
**类型**: 布尔值  
**默认值**: true

是否在达到最大回撤时自动强制平仓。

**建议**：实盘账户强烈建议设置为 `true`

### 使用场景

#### 保守型交易者

```yaml
risk_management:
  max_daily_loss_percent: 2.0
  max_total_risk_percent: 10.0
  max_open_positions: 3
  max_drawdown_percent: 10.0
  force_close_on_max_drawdown: true
```

**特点**：严格风控，保护本金

#### 稳健型交易者（推荐）

```yaml
risk_management:
  max_daily_loss_percent: 5.0
  max_total_risk_percent: 20.0
  max_open_positions: 10
  max_drawdown_percent: 20.0
  force_close_on_max_drawdown: true
```

**特点**：平衡风险和收益

#### 激进型交易者

```yaml
risk_management:
  max_daily_loss_percent: 10.0
  max_total_risk_percent: 30.0
  max_open_positions: 20
  max_drawdown_percent: 30.0
  force_close_on_max_drawdown: true
```

**特点**：追求高收益，承受高风险

### Web界面操作

#### 步骤1：登录系统

访问账户设置页面

#### 步骤2：查看账户列表

页面显示所有配置的交易账户

#### 步骤3：修改风险参数

在"风险控制参数"区域：
1. 输入每日最大亏损百分比
2. 输入总风险百分比
3. 输入最大持仓数
4. 输入最大回撤百分比 ⚠️
5. 勾选强制平仓开关

#### 步骤4：保存设置

点击"保存设置"按钮

#### 步骤5：启用账户

点击"启用"按钮激活账户

### API使用

#### 更新风险设置

```bash
curl -X PUT http://localhost:8686/api/v1/accounts/mt4_demo_001/risk-management \
  -H "Content-Type: application/json" \
  -d '{
    "max_daily_loss_percent": 5.0,
    "max_total_risk_percent": 20.0,
    "max_open_positions": 10,
    "max_drawdown_percent": 20.0,
    "force_close_on_max_drawdown": true
  }'
```

#### 启用/禁用账户

```bash
# 启用
curl -X POST http://localhost:8686/api/v1/accounts/mt4_demo_001/enable

# 禁用
curl -X POST http://localhost:8686/api/v1/accounts/mt4_demo_001/disable
```

#### 获取账户状态

```bash
curl http://localhost:8686/api/v1/accounts/mt4_demo_001/status
```

### 风险状态说明

| 风险状态 | 回撤范围 | 说明 |
|---------|---------|------|
| safe | 0% - 10% | 安全，正常交易 |
| warning | 10% - 16% | 警告，需要关注 |
| critical | 16% - 20% | 危险，接近强平线 |
| force_close | ≥ 20% | 触发强制平仓 |

### 通知机制

#### 回撤警告（80%阈值）

当回撤达到最大回撤的80%时：
```
⚠️ 回撤警告
账户回撤已达16%，接近最大回撤线20%
```

#### 强制平仓通知

当回撤达到最大回撤时：
```
🚨 最大回撤强制平仓
账户回撤达到20%，已强制平仓所有持仓

详情：
- 峰值权益：$12,000
- 当前权益：$9,600
- 回撤：20.0%
- 已平仓持仓：3个
- 账户状态：已暂停
```

---

## 常见问题

### Q1: 如何修改监控间隔？

编辑 `config/risk_config.yaml`，修改 `monitoring` 部分的参数，然后重启系统。

### Q2: 高频模式和标准模式有什么区别？

- **标准模式**：轮询检查，适合低频交易
- **高频模式**：支持毫秒级检查和事件驱动，适合高频交易

### Q3: 事件驱动模式有什么优势？

- 零延迟响应
- 更低的资源消耗
- 适合高频交易场景

### Q4: 如何设置合理的回撤阈值？

建议根据策略特点和风险承受能力：
- 保守型：10-15%
- 稳健型：15-25%
- 激进型：25-35%

### Q5: 强制平仓后如何恢复交易？

1. 分析触发原因
2. 调整策略或参数
3. 在Web界面重新启用账户

### Q6: 可以禁用强制平仓功能吗？

可以，但不建议。在Web界面取消勾选"达到最大回撤时强制平仓"。

### Q7: 系统支持多账户吗？

支持。每个账户可以独立配置风险参数。

### Q8: 如何查看历史风险事件？

查看系统日志文件：`logs/risk_manager.log`

### Q9: 监控间隔最低可以设置多少？

建议不低于50毫秒（0.05秒），过低可能导致系统过载。

### Q10: 如何测试风险控制功能？

运行演示脚本：
```bash
python examples/account_risk_demo.py
```

---

## 最佳实践

### 1. 实盘前测试

- ✅ 在模拟账户充分测试
- ✅ 验证风险参数合理性
- ✅ 观察触发频率
- ✅ 评估对策略的影响

### 2. 动态调整

根据市场情况调整参数：
- 波动大时：降低回撤阈值
- 波动小时：可适当提高
- 重大事件前：收紧风控

### 3. 多账户管理

为不同策略设置不同账户：
- 保守策略：低回撤阈值
- 激进策略：高回撤阈值
- 分散风险

### 4. 定期检查

- 每日检查账户状态
- 每周回顾风险事件
- 每月优化参数设置

### 5. 备份配置

定期备份配置文件：
```bash
cp config/accounts.yaml backups/accounts_$(date +%Y%m%d).yaml
```

---

## 安全注意事项

⚠️ **重要提示**：

1. **实盘账户默认禁用**：需要手动启用
2. **修改需要权限**：只有管理员可以修改风险参数
3. **立即生效**：参数修改后立即生效
4. **不可撤销**：强制平仓后无法恢复持仓
5. **定期备份**：建议定期备份配置文件
6. **测试验证**：修改配置后务必在模拟环境测试

---

## 相关资源

### 文档

- **API文档**：http://localhost:8686/docs
- **数据库完整性指南**：`DATABASE_INTEGRITY_GUIDE.md`
- **部署指南**：`DEPLOYMENT.md`
- **快速部署**：`QUICK_DEPLOY.md`

### 配置文件

- `config/accounts.yaml` - 账户配置
- `config/risk_config.yaml` - 风险控制配置
- `config/ea_config.yaml` - EA执行配置
- `config/factor_config.yaml` - 因子系统配置
- `config/llm_config.yaml` - LLM配置
- `config/push_config.yaml` - 推送通知配置

### 测试脚本

```bash
# 运行所有测试
python test_system.py --all

# 运行数据库检查
python test_system.py --db-check

# 运行风险控制演示
python examples/account_risk_demo.py
```

### 支持

- **GitHub Issues**：https://github.com/feelcharles/OpenFi/issues
- **Email**：support@openfi.local

---

**文档版本**：2.0  
**最后更新**：2026-03-09  
**下次审查**：2026-06-09
