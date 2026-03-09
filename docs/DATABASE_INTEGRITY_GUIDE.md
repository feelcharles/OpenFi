# 数据库完整性检查指南

## 概述

数据库完整性检查功能已集成到 `test_system.py` 中，可以自动检测和验证数据库结构的一致性。

## 使用方法

### 仅检查数据库完整性
```bash
python test_system.py --db-check
```

### 运行完整测试（包括数据库检查）
```bash
python test_system.py --all
```

## 检查项目

### 1. 字段类型一致性
- 检查所有 `user_id` 字段是否为 UUID 类型
- 检查所有 `symbol` 字段是否为 VARCHAR(20)
- 检查所有 JSONB 字段类型
- 检查所有时间戳字段类型

### 2. 外键约束检查
- 验证关键外键的 CASCADE 删除配置
- 检查外键关系的完整性
- 确保数据级联删除正常工作

### 3. 模型与数据库一致性
- 对比 SQLAlchemy 模型定义与实际数据库结构
- 检测缺失的字段
- 检测额外的字段

### 4. 数据流完整性
- 检查孤立的 EA 配置（用户不存在）
- 检查孤立的交易记录（EA 配置不存在）
- 验证数据关联关系

## 测试结果

当前状态：✅ **100% 通过**

- 总测试数：46
- 数据库完整性检查：4/4 通过
- 模块测试：15/15 通过
- 集成测试：7/7 通过
- 协同测试：7/7 通过
- 前端测试：7/7 通过
- 用户工作流：6/6 通过

## 已修复的问题

### 1. ✅ 字段缺失
- `ea_profiles.max_positions` - 已添加

### 2. ✅ 外键约束
- `trades.user_id` - CASCADE
- `trades.ea_profile_id` - CASCADE
- `audit_logs.user_id` - CASCADE
- 其他关键外键 - SET NULL

### 3. ✅ 字段名不一致
- `agents.metadata` → `agents.agent_metadata`

### 4. ✅ 缺失的表
- `alert_logs` - 已创建

### 5. ✅ JSONB 字段更新
- 使用 `flag_modified()` 标记修改

### 6. ✅ 异步 ORM 关联
- 使用 `selectinload()` 预加载

## 数据流验证

### Web → User → EA/Push ✅
用户管理、EA配置、Push配置全部正常

### Fetch → Signal → Notification ✅
数据获取、信号生成、通知推送全部正常

### EA/Factor → Trade ✅
策略执行、交易记录、级联删除全部正常

### Agent 系统 ✅
Agent配置、触发器、Push、Bot连接全部正常

## 维护建议

### 定期检查
```bash
# 每周运行一次完整检查
python test_system.py --all

# 每次数据库迁移后检查
python test_system.py --db-check
```

### 开发流程
1. 修改模型后立即创建迁移
2. 应用迁移后运行数据库检查
3. 确保所有测试通过后再提交代码

### 监控告警
- 设置数据库连接池监控
- 设置外键约束违反告警
- 设置孤立数据检测任务

## 故障排查

### 如果检查失败

1. **字段类型不匹配**
   - 检查迁移文件是否正确
   - 运行 `alembic upgrade head`

2. **外键约束错误**
   - 检查是否有孤立数据
   - 清理孤立数据后重新配置外键

3. **模型不一致**
   - 确保模型定义与数据库同步
   - 创建新的迁移文件

4. **孤立数据**
   - 使用 SQL 查询定位孤立数据
   - 手动清理或修复关联关系

## 技术细节

### 检查实现
所有检查逻辑位于 `test_system.py` 的 `SystemTester` 类中：

- `_check_field_type_consistency()` - 字段类型检查
- `_check_foreign_key_constraints()` - 外键约束检查
- `_check_model_db_consistency()` - 模型一致性检查
- `_check_data_flow_integrity()` - 数据流完整性检查

### 扩展检查
如需添加新的检查项，在 `check_database_integrity()` 方法中添加：

```python
async def check_database_integrity(self):
    integrity_tests = [
        ("检查名称", self._your_check_function),
        # ... 其他检查
    ]
```

## 相关文档

- `test_system.py` - 主测试脚本
- `alembic/versions/` - 数据库迁移文件
- `system_core/database/models.py` - 数据库模型定义

---

**最后更新**: 2026-03-09  
**状态**: ✅ 所有检查通过
