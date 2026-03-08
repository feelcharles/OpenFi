# 账户风险设置文档
# Account Risk Settings Documentation

## 概述 (Overview)

本文档介绍如何在Web界面设置实盘账户的风险控制参数，特别是最大回撤强制平仓功能。

## 访问账户设置页面

### 方式1: 直接访问
```
http://localhost:8686/account_settings.html
```

### 方式2: 通过API
```bash
# 获取所有账户
curl http://localhost:8686/api/v1/accounts/

# 获取特定账户
curl http://localhost:8686/api/v1/accounts/mt4_demo_001
```

## 风险控制参数说明

### 1. 每日最大亏损 (Max Daily Loss)

**参数**: `max_daily_loss_percent`  
**范围**: 0% - 100%  
**默认值**: 5%

当日累计亏损达到此百分比时，系统将暂停当日交易。

**示例**:
- 账户余额: $10,000
- 设置: 5%
- 触发条件: 当日亏损 ≥ $500

### 2. 总风险百分比 (Max Total Risk)

**参数**: `max_total_risk_percent`  
**范围**: 0% - 100%  
**默认值**: 20%

所有持仓的总风险敞口不能超过此百分比。

**示例**:
- 账户余额: $10,000
- 设置: 20%
- 最大敞口: $2,000

### 3. 最大持仓数 (Max Open Positions)

**参数**: `max_open_positions`  
**范围**: 1 - 无限制  
**默认值**: 10

同时持有的最大仓位数量。

### 4. 最大回撤强制平仓 ⚠️ (Max Drawdown Force Close)

**参数**: `max_drawdown_percent`  
**范围**: 0% - 100%  
**默认值**: 20%

**这是最重要的风险控制参数！**

当账户回撤达到此百分比时，系统将：
1. 立即强制平仓所有持仓
2. 发送紧急通知
3. 暂停账户交易

**回撤计算公式**:
```
回撤 = (峰值权益 - 当前权益) / 峰值权益 × 100%
```

**示例**:
- 峰值权益: $12,000
- 当前权益: $9,600
- 回撤: (12,000 - 9,600) / 12,000 = 20%
- 结果: 触发强制平仓

### 5. 强制平仓开关 (Force Close on Max Drawdown)

**参数**: `force_close_on_max_drawdown`  
**类型**: 布尔值 (true/false)  
**默认值**: true

是否在达到最大回撤时自动强制平仓。

**建议**: 实盘账户强烈建议设置为 `true`

## 使用场景

### 场景1: 保守型交易者

```yaml
risk_management:
  max_daily_loss_percent: 2.0
  max_total_risk_percent: 10.0
  max_open_positions: 3
  max_drawdown_percent: 10.0
  force_close_on_max_drawdown: true
```

**特点**:
- 严格的风险控制
- 适合小资金账户
- 保护本金为主

### 场景2: 稳健型交易者

```yaml
risk_management:
  max_daily_loss_percent: 5.0
  max_total_risk_percent: 20.0
  max_open_positions: 10
  max_drawdown_percent: 20.0
  force_close_on_max_drawdown: true
```

**特点**:
- 平衡风险和收益
- 适合中等资金账户
- 系统默认配置

### 场景3: 激进型交易者

```yaml
risk_management:
  max_daily_loss_percent: 10.0
  max_total_risk_percent: 30.0
  max_open_positions: 20
  max_drawdown_percent: 30.0
  force_close_on_max_drawdown: true
```

**特点**:
- 较高的风险承受能力
- 适合大资金账户
- 追求高收益

## Web界面操作步骤

### 步骤1: 登录系统

访问 `http://localhost:8686/account_settings.html`

### 步骤2: 查看账户列表

页面会显示所有配置的交易账户，包括：
- 账户名称
- 账户类型（模拟/实盘）
- 平台信息
- 当前状态

### 步骤3: 修改风险参数

在账户卡片中找到"风险控制参数"部分：

1. **每日最大亏损**: 输入百分比（如 5.0）
2. **总风险百分比**: 输入百分比（如 20.0）
3. **最大持仓数**: 输入整数（如 10）
4. **最大回撤百分比**: 输入百分比（如 20.0）⚠️
5. **强制平仓开关**: 勾选或取消勾选

### 步骤4: 保存设置

点击"保存设置"按钮，系统会：
- 验证参数有效性
- 更新配置文件
- 显示成功提示

### 步骤5: 启用/禁用账户

- 点击"启用"按钮激活账户
- 点击"禁用"按钮停用账户

## API使用示例

### 更新风险设置

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

### 启用账户

```bash
curl -X POST http://localhost:8686/api/v1/accounts/mt4_demo_001/enable
```

### 禁用账户

```bash
curl -X POST http://localhost:8686/api/v1/accounts/mt4_demo_001/disable
```

### 获取账户状态

```bash
curl http://localhost:8686/api/v1/accounts/mt4_demo_001/status
```

响应示例:
```json
{
  "account_id": "mt4_demo_001",
  "enabled": true,
  "current_balance": 10000.0,
  "current_equity": 9500.0,
  "current_drawdown_percent": 5.0,
  "open_positions": 3,
  "daily_pnl": -500.0,
  "daily_pnl_percent": -5.0,
  "risk_status": "warning",
  "last_updated": "2026-03-09T02:00:00"
}
```

## 风险状态说明

系统会根据当前回撤自动评估风险状态：

| 风险状态 | 回撤范围 | 说明 |
|---------|---------|------|
| **safe** | 0% - 10% | 安全，正常交易 |
| **warning** | 10% - 16% | 警告，需要关注 |
| **critical** | 16% - 20% | 危险，接近强平线 |
| **force_close** | ≥ 20% | 触发强制平仓 |

## 通知机制

### 回撤警告 (80%阈值)

当回撤达到最大回撤的80%时：
- 发送警告通知
- 建议减少仓位
- 不会自动平仓

**示例**: 最大回撤20%，当回撤达到16%时发送警告

### 强制平仓通知

当回撤达到最大回撤时：
- 发送紧急通知（高优先级）
- 自动平仓所有持仓
- 暂停账户交易
- 记录详细日志

## 监控和日志

### 实时监控

系统每10秒检查一次账户回撤：
```python
# 监控频率
check_interval = 10  # 秒
```

### 日志记录

所有风险事件都会记录日志：
```
2026-03-09 02:00:00 [WARNING] drawdown_warning: 回撤16%, 接近阈值20%
2026-03-09 02:05:00 [CRITICAL] max_drawdown_triggered: 回撤20%, 强制平仓
```

## 最佳实践

### 1. 实盘账户设置建议

- ✅ 设置合理的最大回撤（建议15-25%）
- ✅ 启用强制平仓功能
- ✅ 定期检查账户状态
- ✅ 关注回撤警告通知

### 2. 模拟账户测试

在实盘前，先在模拟账户测试：
1. 设置不同的回撤阈值
2. 观察触发频率
3. 评估对策略的影响
4. 找到最优参数

### 3. 动态调整

根据市场情况调整参数：
- 波动大时：降低回撤阈值
- 波动小时：可适当提高
- 重大事件前：收紧风控

### 4. 多账户管理

为不同策略设置不同账户：
- 保守策略：低回撤阈值
- 激进策略：高回撤阈值
- 分散风险

## 故障排除

### 问题1: 无法保存设置

**原因**: 权限不足  
**解决**: 确保使用管理员账户登录

### 问题2: 强制平仓未触发

**原因**: 
- 未启用强制平仓开关
- 权益数据未更新

**解决**:
1. 检查 `force_close_on_max_drawdown` 是否为 true
2. 确认系统正在接收权益更新事件

### 问题3: 频繁触发警告

**原因**: 回撤阈值设置过低  
**解决**: 适当提高 `max_drawdown_percent`

## 安全注意事项

⚠️ **重要提示**:

1. **实盘账户默认禁用**: 需要手动启用
2. **修改需要权限**: 只有管理员可以修改风险参数
3. **立即生效**: 参数修改后立即生效
4. **不可撤销**: 强制平仓后无法恢复持仓
5. **定期备份**: 建议定期备份配置文件

## 相关文档

- [端到端工作流](./END_TO_END_WORKFLOW.md)
- [风险控制配置](../config/risk_config.yaml)
- [账户配置](../config/accounts.yaml)
- [API文档](../API.md)

---

**最后更新**: 2026-03-09  
**版本**: 1.0.0
