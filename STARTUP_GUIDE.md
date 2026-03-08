# OpenFi 启动指南 / Startup Guide

## 🚀 一键启动 / One-Click Start

### Linux/Unix 系统

部署完成后，使用以下命令启动服务器：

```bash
systemctl start openfi
```

其他管理命令：

```bash
# 停止服务器
systemctl stop openfi

# 重启服务器
systemctl restart openfi

# 查看服务状态
systemctl status openfi

# 查看实时日志
journalctl -u openfi -f
```

### Windows 系统

双击运行 `start.bat` 文件，或在命令行中执行：

```cmd
start.bat
```

这将自动：
1. 检查 Docker 服务
2. 启动 PostgreSQL 和 Redis
3. 启动 OpenFi Web 服务器

### Docker Compose 方式

如果使用 Docker Compose 部署：

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

## 📱 访问地址

部署完成后，可以通过以下地址访问：

- **主应用**: http://localhost:8686/app
- **API 文档**: http://localhost:8686/docs
- **健康检查**: http://localhost:8686/health

如果是远程服务器，将 `localhost` 替换为服务器 IP 地址。

## 🔐 默认账户

- **用户名**: admin
- **密码**: admin123
- ⚠️ **首次登录必须修改密码**

## 🛠️ 故障排查

### 服务无法启动

1. 检查所有依赖服务是否运行：
   ```bash
   # Linux
   systemctl status postgresql redis nginx openfi
   
   # Windows
   docker-compose ps
   ```

2. 查看详细日志：
   ```bash
   # Linux
   journalctl -u openfi -n 100 --no-pager
   
   # Windows
   docker-compose logs openfi
   ```

3. 检查端口占用：
   ```bash
   # Linux
   ss -tlnp | grep 8686
   
   # Windows
   netstat -ano | findstr :8686
   ```

### 数据库连接失败

1. 确认 PostgreSQL 正在运行：
   ```bash
   # Linux
   systemctl status postgresql
   
   # Windows
   docker-compose ps postgres
   ```

2. 测试数据库连接：
   ```bash
   psql -h localhost -U openfi -d openfi
   ```

### Redis 连接失败

1. 确认 Redis 正在运行：
   ```bash
   # Linux
   systemctl status redis
   
   # Windows
   docker-compose ps redis
   ```

2. 测试 Redis 连接：
   ```bash
   redis-cli ping
   ```

## 🔄 重置系统

⚠️ **危险操作** - 这将删除所有数据！

```bash
# Linux
sudo bash /opt/openfi/scripts/reset_system.sh

# Windows
# 停止所有服务
docker-compose down -v
# 删除数据卷
docker volume prune -f
```

## 📚 更多信息

- [完整文档](README.md)
- [API 文档](API.md)
- [部署指南](DEPLOYMENT.md)
- [快速参考](QUICK_REFERENCE.md)

## 💡 提示

- 生产环境建议使用 systemd 服务管理（Linux）
- 开发环境可以直接使用 `python -m uvicorn` 命令
- 确保防火墙允许 8686 端口访问
- 定期备份数据库和配置文件

---

**版本**: 1.0.0  
**更新时间**: 2026-03-09
