# Agent System Module

多Agent管理系统，作为OpenFi Lite的子模块集成。

## 概述

Agent System允许用户创建和管理多个独立的Agent，每个Agent可以高度定制：
- 功能权限（信息检索、AI分析、回测、推送通知、EA推荐）
- 资产组合（监控的品种和权重）
- 触发条件（关键词、因子、价格、价格变化、时间、手动）
- 推送配置（频率限制、静默时段、消息模板）
- Bot连接（Telegram、Discord、Slack等，每个Agent最多5个）

## 架构

### 核心组件

1. **AgentManager** (`manager.py`)
   - Agent生命周期管理（CRUD操作）
   - Agent状态管理（active, inactive, paused, error）
   - Agent克隆和模板功能
   - 配置版本控制

2. **AgentExecutor** (`executor.py`)
   - Agent触发事件执行
   - 权限检查和去重
   - 配额管理
   - 集成AI引擎、因子系统、执行引擎、推送系统

3. **ConfigManager** (`config_manager.py`)
   - 配置持久化和缓存（Redis，TTL 5分钟）
   - 配置验证和版本控制
   - 配置导入导出（JSON/YAML）
   - 配置热重载（5秒内检测变更）

4. **AgentIsolator** (`isolator.py`)
   - Agent数据隔离机制
   - 访问权限验证
   - 访问审计日志
   - 缓存键agent_id前缀

### 数据模型

数据库表（在 `system_core/database/models.py`）：
- `agents` - Agent基本信息
- `agent_configs` - Agent配置（带版本控制）
- `agent_assets` - Agent资产组合
- `agent_triggers` - Agent触发配置
- `agent_push_configs` - Agent推送配置
- `agent_bot_connections` - Agent Bot连接
- `agent_metrics` - Agent性能指标
- `agent_logs` - Agent日志

Pydantic模型（在 `models.py`）：
- `AgentCreate`, `AgentUpdate`, `Agent` - Agent实体
- `AgentConfig` - 完整配置
- `AgentPermissions` - 功能权限
- `AssetPortfolio`, `AssetWeight` - 资产组合
- `TriggerConfig`, `TriggerEvent` - 触发配置
- `PushConfig` - 推送配置
- `BotConnection` - Bot连接
- `ResourceQuotas` - 资源配额

## API端点

所有API端点在 `system_core/web_backend/agent_api.py`，前缀 `/api/v1/agents`。

### Agent管理
- `POST /` - 创建Agent
- `GET /` - 列出Agents（支持过滤和分页）
- `GET /{id}` - 获取Agent详情
- `PUT /{id}` - 更新Agent
- `DELETE /{id}` - 删除Agent
- `POST /{id}/clone` - 克隆Agent
- `PUT /{id}/state` - 改变Agent状态

### 配置管理
- `GET /{id}/config` - 获取配置
- `PUT /{id}/config` - 更新配置
- `GET /{id}/config/versions` - 获取配置版本列表
- `GET /{id}/config/versions/{version}` - 获取特定版本
- `POST /{id}/config/rollback` - 回滚配置
- `POST /{id}/config/validate` - 验证配置

### 资产管理
- `GET /{id}/assets` - 获取资产组合
- `PUT /{id}/assets` - 更新资产组合
- `POST /{id}/assets` - 添加资产
- `DELETE /{id}/assets/{symbol}` - 删除资产

### 触发管理
- `GET /{id}/triggers` - 获取触发配置
- `PUT /{id}/triggers` - 更新触发配置
- `POST /{id}/triggers/test` - 测试触发

### 推送配置
- `GET /{id}/push-config` - 获取推送配置
- `PUT /{id}/push-config` - 更新推送配置

### Bot连接
- `GET /{id}/bots` - 获取Bot连接列表
- `POST /{id}/bots` - 添加Bot连接
- `PUT /{id}/bots/{bot_id}` - 更新Bot连接
- `DELETE /{id}/bots/{bot_id}` - 删除Bot连接
- `POST /{id}/bots/{bot_id}/test` - 测试Bot连接

### 监控
- `GET /{id}/status` - 获取运行状态
- `GET /{id}/metrics` - 获取性能指标
- `GET /{id}/logs` - 获取日志
- `GET /{id}/alerts` - 获取告警

## 认证和授权

所有API端点需要JWT Bearer token认证，并使用RBAC权限模型：
- `agent:create` - 创建Agent
- `agent:read` - 读取Agent信息
- `agent:update` - 更新Agent
- `agent:delete` - 删除Agent

## 使用示例

### 创建Agent

```python
import httpx

# 创建Agent
response = httpx.post(
    "http://localhost:8000/api/v1/agents",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "name": "forex_monitor",
        "description": "监控外汇市场",
        "priority": "high",
        "category": "forex",
        "tags": ["forex", "realtime"],
        "config": {
            "permissions": {
                "info_retrieval": "full_access",
                "ai_analysis": "full_access",
                "push_notification": "full_access"
            },
            "asset_portfolio": {
                "assets": [
                    {"symbol": "EURUSD", "weight": 0.5, "category": "forex"},
                    {"symbol": "GBPUSD", "weight": 0.5, "category": "forex"}
                ]
            },
            "trigger_config": {
                "keywords": {"enabled": True, "keywords": ["美联储", "加息"]},
                "time": {"enabled": True, "schedule": "0 9 * * *"}
            }
        }
    }
)
agent = response.json()
print(f"Created agent: {agent['id']}")
```

### 更新配置

```python
# 更新Agent配置
response = httpx.put(
    f"http://localhost:8000/api/v1/agents/{agent_id}/config",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "permissions": {...},
        "asset_portfolio": {...},
        "trigger_config": {...}
    },
    params={"change_description": "Updated trigger configuration"}
)
```

### 克隆Agent

```python
# 克隆Agent
response = httpx.post(
    f"http://localhost:8000/api/v1/agents/{agent_id}/clone",
    headers={"Authorization": f"Bearer {token}"},
    json={"new_name": "forex_monitor_copy"}
)
cloned_agent = response.json()
```

## 集成

Agent System集成了以下现有模块：
- **database** - 数据库连接和ORM
- **auth** - 认证和授权
- **event_bus** - 事件总线（触发事件）
- **monitoring** - 监控和告警
- **ai_engine** - AI分析
- **factor_system** - 因子计算
- **execution_engine** - 交易执行
- **user_center** - 推送通知
- **fetch_engine** - 新闻和市场数据获取
- **config/keywords** - 关键词和资产配置

## 性能要求

- 支持100+并发Agent
- 触发响应时间<500ms
- 推送延迟<2秒
- 配置查询<100ms
- 配置热重载<5秒

## 数据隔离

每个Agent的数据完全隔离：
- 数据库查询自动添加agent_id过滤
- 缓存键使用agent_id前缀
- 所有访问尝试记录审计日志

## 配置热重载

配置变更在5秒内自动检测并重载：
- 使用PostgreSQL NOTIFY/LISTEN监听变更
- 重载前验证新配置
- 重载失败自动回滚

## 测试

测试文件位于 `tests/`：
- `test_agent_manager.py` - AgentManager单元测试
- `test_agent_executor.py` - AgentExecutor单元测试
- `test_config_manager.py` - ConfigManager单元测试（15个测试全部通过）
- `test_agent_isolator.py` - AgentIsolator单元测试（13个测试全部通过）
- `test_agent_system_integration.py` - 集成测试

运行测试：
```bash
pytest tests/test_agent_*.py -v
```

## 下一步

待实现功能：
- [ ] 事件总线集成（Task 4）
- [ ] 推送系统集成（Task 5）
- [ ] 监控和性能优化（Task 6）
- [ ] Agent模板系统（Task 7）
- [ ] Web前端集成（Task 8）
- [ ] 集成测试和文档（Task 9）

## 贡献

请参考主项目的贡献指南。

## 许可

与主项目相同。
