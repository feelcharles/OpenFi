# OpenFi 系统测试文档
# System Testing Documentation

## 概述 (Overview)

`test_system.py` 是一个全面的系统测试脚本，用于测试和排查 OpenFi 系统的所有模块、集成和功能。

## 功能特性 (Features)

### 1. 模块测试 (Module Tests)
测试系统的每个核心模块和子模块：

- **配置模块** (Config): 配置加载、配置管理器、配置文件读取
- **数据库模块** (Database): 数据库连接、会话管理、模型定义
- **事件总线** (Event Bus): 发布订阅、事件处理、消息传递
- **认证模块** (Auth): 密码哈希、JWT令牌、RBAC权限
- **AI引擎** (AI Engine): LLM客户端、AI处理引擎
- **数据获取引擎** (Fetch Engine): 数据源管理、数据获取
- **因子系统** (Factor System): 因子库、因子计算
- **回测模块** (Backtest): 回测引擎、策略测试
- **执行引擎** (Execution Engine): 交易执行、订单管理
- **监控模块** (Monitoring): 指标收集、健康检查
- **安全模块** (Security): 安全管理、限流器
- **备份模块** (Backup): 备份管理、数据恢复
- **智能体系统** (Agent System): 智能体管理、智能体执行
- **用户中心** (User Center): 用户管理
- **增强模块** (Enhancement): 工具管理

### 2. 事件总线集成测试 (Event Bus Integration)
测试事件总线的集成和端到端工作流：

- **基本发布订阅**: 测试事件发布和订阅机制
- **多订阅者**: 测试多个订阅者接收同一事件
- **事件过滤**: 测试基于条件的事件过滤
- **死信队列**: 测试失败事件的处理
- **事件持久化**: 测试事件的持久化存储
- **事件重试**: 测试失败事件的重试机制
- **端到端工作流**: 测试完整的数据处理流程（数据获取 → AI分析 → 交易执行）

### 3. 模块协同测试 (Module Collaboration)
测试模块间的协同工作、信息共享和数据库操作：

- **配置共享**: 测试配置在模块间的共享（单例模式）
- **数据库共享**: 测试数据库连接池和会话管理
- **缓存共享**: 测试缓存在模块间的共享
- **模块间通信**: 测试通过事件总线的模块间通信
- **数据流转**: 测试数据在多个模块间的流转
- **状态同步**: 测试系统状态在模块间的同步
- **资源管理**: 测试连接池等资源的管理

### 4. 前端和Bot测试 (Frontend & Bot)
测试Web前端和Bot功能：

- **Web服务器**: 测试服务器是否正常运行
- **API端点**: 测试各个API端点的可访问性
- **WebSocket**: 测试WebSocket连接和通信
- **静态文件**: 测试静态文件服务
- **认证流程**: 测试登录和token认证
- **Bot命令**: 测试Bot命令解析
- **Bot响应**: 测试Bot命令响应

## 使用方法 (Usage)

### 基本用法

```bash
# 运行所有测试
python test_system.py --all

# 仅测试模块
python test_system.py --modules

# 仅测试事件总线集成
python test_system.py --eventbus

# 仅测试模块协同
python test_system.py --collaboration

# 仅测试前端
python test_system.py --frontend

# 仅测试Bot
python test_system.py --bot

# 详细输出模式
python test_system.py --all --verbose
```

### 组合使用

```bash
# 测试模块和集成
python test_system.py --modules --integration

# 测试前端和Bot
python test_system.py --frontend --bot

# 测试所有内容（详细模式）
python test_system.py --all -v
```

## 前置条件 (Prerequisites)

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境

确保 `.env` 文件已正确配置：

```bash
cp .env.example .env
# 编辑 .env 文件，填入必要的配置
```

### 3. 启动必要服务

某些测试需要以下服务运行：

```bash
# 启动数据库（PostgreSQL）
# 启动Redis
# 启动Web服务器（用于前端测试）
python -m uvicorn system_core.web_backend.app:app --host 0.0.0.0 --port 8686
```

## 测试报告 (Test Reports)

### 控制台输出

测试运行时会实时显示：
- ✓ 通过的测试（绿色）
- ✗ 失败的测试（红色）
- ○ 跳过的测试（黄色）

### 测试报告文件

测试完成后会生成详细报告：
- 位置: `test_results/test_report_YYYYMMDD_HHMMSS.txt`
- 包含: 所有测试结果、错误信息、统计数据

### 报告内容

```
总体统计:
- 总测试数
- 通过数量
- 失败数量
- 错误数量
- 跳过数量
- 成功率
- 总耗时

模块详情:
- 每个模块的测试结果
- 失败和错误的详细信息
```

## Bug排查指南 (Debugging Guide)

### 1. 模块导入错误

**问题**: `ImportError: No module named 'xxx'`

**解决方案**:
```bash
# 检查依赖是否安装
pip install -r requirements.txt

# 检查Python路径
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### 2. 数据库连接失败

**问题**: 数据库连接失败

**解决方案**:
```bash
# 检查数据库是否运行
pg_isready

# 检查配置
cat .env | grep DATABASE_URL

# 初始化数据库
python scripts/db_migrate.py
```

### 3. Redis连接失败

**问题**: 事件总线连接失败

**解决方案**:
```bash
# 检查Redis是否运行
redis-cli ping

# 检查配置
cat .env | grep REDIS_URL
```

### 4. Web服务器未运行

**问题**: 前端测试失败，无法连接到服务器

**解决方案**:
```bash
# 启动Web服务器
python -m uvicorn system_core.web_backend.app:app --host 0.0.0.0 --port 8686

# 或使用启动脚本
./start.sh  # Linux/Mac
start.bat   # Windows
```

### 5. 权限问题

**问题**: 文件或目录权限不足

**解决方案**:
```bash
# 检查文件权限
ls -la

# 修改权限
chmod +x test_system.py
```

## 持续集成 (CI/CD)

### GitHub Actions 示例

```yaml
name: System Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        python test_system.py --all --verbose
```

## 最佳实践 (Best Practices)

### 1. 定期运行测试

```bash
# 每次代码变更后
python test_system.py --all

# 部署前
python test_system.py --all --verbose
```

### 2. 隔离测试环境

```bash
# 使用虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 使用测试数据库
export DATABASE_URL="postgresql://user:pass@localhost/test_db"
```

### 3. 监控测试性能

```bash
# 使用详细模式查看耗时
python test_system.py --all -v

# 关注慢速测试
# 查看报告中的duration字段
```

### 4. 处理测试失败

1. 查看详细错误信息（使用 `--verbose`）
2. 检查相关服务是否运行
3. 验证配置文件
4. 查看日志文件
5. 隔离问题模块单独测试

## 扩展测试 (Extending Tests)

### 添加新的模块测试

```python
async def _test_new_module(self):
    """测试新模块"""
    from system_core.new_module import NewModule
    
    # 初始化
    new_module = NewModule()
    await new_module.initialize()
    
    # 测试功能
    result = await new_module.do_something()
    assert result is not None, "功能测试失败"
    
    # 清理
    await new_module.close()
```

然后在 `test_all_modules` 中添加：

```python
modules_to_test = [
    # ... 现有模块 ...
    ("new_module", self._test_new_module),
]
```

### 添加新的集成测试

```python
async def _test_new_integration(self):
    """测试新的集成场景"""
    # 实现测试逻辑
    pass
```

然后在 `test_event_bus_integration` 或 `test_module_collaboration` 中添加。

## 故障排除 (Troubleshooting)

### 常见问题

1. **测试超时**: 增加超时时间或检查服务响应
2. **间歇性失败**: 检查异步操作的等待时间
3. **资源泄漏**: 确保所有资源正确清理
4. **并发问题**: 使用适当的锁和同步机制

### 获取帮助

- 查看日志文件: `logs/`
- 查看测试报告: `test_results/`
- 提交Issue: GitHub Issues
- 查看文档: `docs/`

## 性能基准 (Performance Benchmarks)

典型测试耗时（参考）：

- 模块测试: ~30-60秒
- 事件总线集成: ~10-20秒
- 模块协同: ~15-30秒
- 前端和Bot: ~10-20秒
- 总计: ~65-130秒

## 许可证 (License)

MIT License - 详见 [LICENSE](LICENSE) 文件

---

**最后更新**: 2026-03-09
**版本**: 1.0.0
