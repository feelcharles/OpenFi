# EA Folder / EA文件夹

[English](#english) | [中文](#chinese)

---

<a name="english"></a>
## English

### Overview

This folder stores your Expert Advisor (EA) files. The system supports EAs for three trading platforms:

- **MT4**: `.ex4` (compiled) and `.mq4` (source code)
- **MT5**: `.ex5` (compiled) and `.mq5` (source code)
- **TradingView**: `.pine` (Pine Script)

### Folder Structure

```
ea/
├── README.md              # This file
├── .gitignore            # Git ignore configuration
├── logs/                  # EA test logs folder
│   └── ea_log_{name}.txt  # Test log files
└── (Your EA files here)
```

**Note**: The `logs/` folder is automatically excluded from EA scanning.

### How to Use

#### 1. Upload EA Files

Copy your EA files directly to the `ea/` folder. You can:

- Place them in the root directory
- Create subfolders to organize EA files (e.g., `ea/scalpers/`, `ea/trend_followers/`)

Supported file formats:
- MT4: `.ex4`, `.mq4`
- MT5: `.ex5`, `.mq5`
- TradingView: `.pine`

#### 2. Refresh EA List

After uploading EA files, run the following command to scan and update the EA list:

```bash
# Using Python script
python scripts/ea_refresh.py

# Or using Bot command (in chat interface)
/ea_refresh
```

The system will:
- Scan `ea/` folder and all subfolders
- Identify all supported EA files
- Extract EA metadata (name, version, author, etc.)
- Update `config/ea_config.yaml` configuration file

#### 3. Test EA

Test if EA has errors:

```bash
# Using Bot command
/ea_test {ea_name}

# Example:
/ea_test example_scalper
```

Test results are saved in `ea/logs/ea_log_{ea_name}.txt`.

### EA Metadata

The system attempts to extract the following metadata from EA source code:

#### MT4/MT5 EA

Use the following format in source code:

```mql4
#property copyright "Your Name"
#property version   "1.0.0"
#property description "EA description"

// Or use comments
// @author Your Name
// @version 1.0.0
// @description EA description
```

#### TradingView Pine Script

```pine
//@version=5
// @author Your Name
// @version 1.0.0
// @description Strategy description

strategy("Strategy Name", overlay=true)
```

### Configuration File

EA information is automatically saved to `config/ea_config.yaml`, including:

- `ea_id`: EA unique identifier
- `ea_name`: EA name
- `ea_type`: Platform type (mt4, mt5, tradingview)
- `file_path`: File path
- `description`: EA description
- `author`: Author
- `version`: Version number
- `performance`: Performance statistics

### Notes

1. **File Naming**: Use English letters, numbers, underscores, and hyphens for EA file names
2. **File Size**: System records file size and last modified time
3. **Auto Update**: Each time `/ea_refresh` runs, the system will:
   - Add newly discovered EAs
   - Update existing EA file information
   - Remove deleted EAs
   - Preserve EA performance statistics

4. **Test Logs**: All test logs are saved in `ea/logs/` folder for troubleshooting

### Example

#### Adding New EA

1. Copy EA file to `ea/` folder
2. Run `/ea_refresh` to refresh list
3. Run `/ea_test {name}` to test EA
4. Check `ea/logs/ea_log_{name}.txt` for test results

#### Organizing EA Files

```
ea/
├── scalpers/
│   ├── scalper_v1.mq4
│   └── scalper_v2.mq4
├── trend_followers/
│   ├── trend_ma.mq5
│   └── trend_breakout.mq5
└── tradingview/
    ├── momentum_strategy.pine
    └── mean_reversion.pine
```

After running `/ea_refresh`, the system automatically scans all subfolders.

### Troubleshooting

#### EA Not Recognized

- Check if file extension is correct
- Ensure file is not hidden
- Run `/ea_refresh` to rescan

#### Test Failed

- Check `ea/logs/ea_log_{name}.txt` for detailed error information
- Verify EA code syntax
- Ensure EA uses valid API functions

#### Metadata Not Extracted

- Check comment format in source code
- System uses filename as default EA name
- Manually edit `config/ea_config.yaml` to add metadata

### Support

For issues, check:
- System logs
- EA test logs (`ea/logs/`)
- Configuration file (`config/ea_config.yaml`)

---

<a name="chinese"></a>
## 中文

### 概述

此文件夹用于存储您的Expert Advisor (EA) 文件。系统支持三种交易平台的EA：

- **MT4**: `.ex4`（编译版）和 `.mq4`（源代码）
- **MT5**: `.ex5`（编译版）和 `.mq5`（源代码）
- **TradingView**: `.pine`（Pine脚本）

### 文件夹结构

```
ea/
├── README.md              # 本说明文件
├── .gitignore            # Git忽略配置
├── logs/                  # EA测试日志文件夹
│   └── ea_log_{name}.txt  # 测试日志文件
└── (您的EA文件放在这里)
```

**注意**: `logs/` 文件夹会被自动排除，不会被扫描到EA列表中。

### 如何使用

#### 1. 上传EA文件

将您的EA文件直接复制到 `ea/` 文件夹中。您可以：

- 直接放在根目录
- 创建子文件夹来组织EA文件（例如：`ea/scalpers/`、`ea/trend_followers/`）

支持的文件格式：
- MT4: `.ex4`、`.mq4`
- MT5: `.ex5`、`.mq5`
- TradingView: `.pine`

#### 2. 刷新EA列表

上传EA文件后，运行以下命令来扫描并更新EA列表：

```bash
# 使用Python脚本
python scripts/ea_refresh.py

# 或使用Bot命令（在聊天界面）
/ea_refresh
```

系统会：
- 扫描 `ea/` 文件夹及所有子文件夹
- 识别所有支持的EA文件
- 提取EA元数据（名称、版本、作者等）
- 更新 `config/ea_config.yaml` 配置文件

#### 3. 测试EA

测试EA是否有错误：

```bash
# 使用Bot命令
/ea_test {ea名称}

# 例如：
/ea_test example_scalper
```

测试结果会保存在 `ea/logs/ea_log_{ea名称}.txt` 文件中。

### EA元数据

系统会尝试从EA源代码中提取以下元数据：

#### MT4/MT5 EA

在源代码中使用以下格式：

```mql4
#property copyright "Your Name"
#property version   "1.0.0"
#property description "EA description"

// 或使用注释
// @author Your Name
// @version 1.0.0
// @description EA description
```

#### TradingView Pine脚本

```pine
//@version=5
// @author Your Name
// @version 1.0.0
// @description Strategy description

strategy("Strategy Name", overlay=true)
```

### 配置文件

EA信息会自动保存到 `config/ea_config.yaml` 文件中，包含：

- `ea_id`: EA唯一标识符
- `ea_name`: EA名称
- `ea_type`: 平台类型（mt4、mt5、tradingview）
- `file_path`: 文件路径
- `description`: EA描述
- `author`: 作者
- `version`: 版本号
- `performance`: 性能统计数据

### 注意事项

1. **文件命名**: 建议使用英文字母、数字、下划线和连字符命名EA文件
2. **文件大小**: 系统会记录文件大小和最后修改时间
3. **自动更新**: 每次运行 `/ea_refresh` 时，系统会：
   - 添加新发现的EA
   - 更新已存在EA的文件信息
   - 移除已删除的EA
   - 保留EA的性能统计数据

4. **测试日志**: 所有测试日志保存在 `ea/logs/` 文件夹中，便于问题诊断

### 示例

#### 添加新EA

1. 将EA文件复制到 `ea/` 文件夹
2. 运行 `/ea_refresh` 刷新列表
3. 运行 `/ea_test {名称}` 测试EA
4. 查看 `ea/logs/ea_log_{名称}.txt` 了解测试结果

#### 组织EA文件

```
ea/
├── scalpers/
│   ├── scalper_v1.mq4
│   └── scalper_v2.mq4
├── trend_followers/
│   ├── trend_ma.mq5
│   └── trend_breakout.mq5
└── tradingview/
    ├── momentum_strategy.pine
    └── mean_reversion.pine
```

运行 `/ea_refresh` 后，系统会自动扫描所有子文件夹。

### 故障排除

#### EA未被识别

- 检查文件扩展名是否正确
- 确保文件不是隐藏文件
- 运行 `/ea_refresh` 重新扫描

#### 测试失败

- 查看 `ea/logs/ea_log_{名称}.txt` 了解详细错误信息
- 检查EA代码语法
- 确保EA使用的API函数有效

#### 元数据未提取

- 检查源代码中的注释格式
- 系统会使用文件名作为默认EA名称
- 可以手动编辑 `config/ea_config.yaml` 添加元数据

### 技术支持

如有问题，请查看：
- 系统日志
- EA测试日志（`ea/logs/`）
- 配置文件（`config/ea_config.yaml`）

