# OpenFi 部署故障排查指南

## 常见问题和解决方案

### 1. 找不到 verify_migrations.py 文件

**错误信息：**
```
python: can't open file '/opt/openfi/scripts/verify_migrations.py': [Errno 2] No such file or directory
```

**原因：**
- 服务器上的代码仓库未正确更新
- Git pull 失败但脚本继续执行

**解决方案：**

```bash
# 方案1: 手动更新代码
cd /opt/openfi
git fetch origin
git reset --hard origin/main

# 方案2: 删除并重新克隆
rm -rf /opt/openfi
git clone https://github.com/feelcharles/OpenFi.git /opt/openfi

# 方案3: 重新运行部署脚本（推荐）
bash quick_deploy.sh
```

### 2. 数据库连接失败

**错误信息：**
```
[ERROR] 数据库连接失败
```

**检查步骤：**

```bash
# 1. 检查 PostgreSQL 服务状态
systemctl status postgresql

# 2. 检查 PostgreSQL 是否监听
ss -tlnp | grep 5432

# 3. 测试数据库连接
cd /opt/openfi
source venv/bin/activate
python scripts/test_db_connection.py

# 4. 检查 pg_hba.conf 配置
sudo -u postgres psql -t -P format=unaligned -c 'SHOW hba_file;'
```

**解决方案：**

```bash
# 重启 PostgreSQL
systemctl restart postgresql

# 重新配置数据库（如果需要）
sudo -u postgres psql -c "ALTER USER openfi WITH PASSWORD 'your_password';"

# 更新 .env 文件中的数据库密码
nano /opt/openfi/.env
```

### 3. Redis 连接失败

**错误信息：**
```
[ERROR] 事件总线连接失败
```

**检查步骤：**

```bash
# 检查 Redis 服务状态
systemctl status redis
# 或
systemctl status redis-server

# 检查 Redis 是否监听
ss -tlnp | grep 6379

# 测试 Redis 连接
redis-cli ping
```

**解决方案：**

```bash
# 启动 Redis
systemctl start redis
# 或
systemctl start redis-server

# 设置开机自启
systemctl enable redis
```

### 4. 迁移链验证失败

**错误信息：**
```
[ERROR] 迁移链验证失败
```

**检查步骤：**

```bash
cd /opt/openfi
source venv/bin/activate
python scripts/verify_migrations.py
```

**可能的问题：**
- 迁移文件缺失
- 迁移链有循环依赖
- 迁移链有分支

**解决方案：**

```bash
# 查看迁移文件
ls -la alembic/versions/

# 检查迁移历史
alembic history

# 如果需要，重置数据库并重新迁移
# ⚠️ 警告：这会删除所有数据
sudo -u postgres psql -c "DROP DATABASE openfi;"
sudo -u postgres psql -c "CREATE DATABASE openfi;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE openfi TO openfi;"
alembic upgrade head
```

### 5. OpenFi 服务启动失败

**错误信息：**
```
[ERROR] OpenFi服务启动失败
```

**检查步骤：**

```bash
# 查看服务状态
systemctl status openfi

# 查看详细日志
journalctl -u openfi -n 100 --no-pager

# 查看最近的错误
journalctl -u openfi -p err -n 50
```

**常见原因和解决方案：**

#### 端口被占用
```bash
# 检查 8686 端口
ss -tlnp | grep 8686

# 如果被占用，找到进程并停止
lsof -i :8686
kill -9 <PID>
```

#### 依赖缺失
```bash
cd /opt/openfi
source venv/bin/activate
pip install -r requirements.txt
```

#### 配置文件错误
```bash
# 检查 .env 文件
cat /opt/openfi/.env

# 验证配置
cd /opt/openfi
source venv/bin/activate
python scripts/validate_config.py
```

### 6. Nginx 配置问题

**错误信息：**
```
502 Bad Gateway
```

**检查步骤：**

```bash
# 检查 Nginx 状态
systemctl status nginx

# 测试 Nginx 配置
nginx -t

# 查看 Nginx 错误日志
tail -f /var/log/nginx/error.log

# 检查后端服务
curl http://localhost:8686/health
```

**解决方案：**

```bash
# 重启 Nginx
systemctl restart nginx

# 如果配置有问题，重新生成
bash quick_deploy.sh  # 会自动重新配置 Nginx
```

### 7. 防火墙问题

**症状：**
- 本地可以访问，但外部无法访问

**检查步骤：**

```bash
# 检查防火墙状态（CentOS/RHEL）
firewall-cmd --list-all

# 检查防火墙状态（Ubuntu/Debian）
ufw status

# 检查端口监听
ss -tlnp | grep -E ':(80|8686)'
```

**解决方案：**

```bash
# CentOS/RHEL
firewall-cmd --permanent --add-port=80/tcp
firewall-cmd --permanent --add-port=8686/tcp
firewall-cmd --reload

# Ubuntu/Debian
ufw allow 80/tcp
ufw allow 8686/tcp
```

### 8. SELinux 问题

**症状：**
- Nginx 无法连接到后端服务
- 权限被拒绝错误

**检查步骤：**

```bash
# 检查 SELinux 状态
getenforce

# 查看 SELinux 日志
ausearch -m avc -ts recent
```

**解决方案：**

```bash
# 允许 Nginx 网络连接
setsebool -P httpd_can_network_connect 1

# 如果问题持续，临时禁用 SELinux（不推荐用于生产环境）
setenforce 0

# 永久禁用（需要重启）
sed -i 's/SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config
```

## 完整的健康检查脚本

创建一个健康检查脚本：

```bash
#!/bin/bash
# health_check.sh

echo "=== OpenFi 健康检查 ==="
echo ""

# 检查服务状态
echo "1. 服务状态："
for service in postgresql redis nginx openfi; do
    if systemctl is-active $service &> /dev/null; then
        echo "  ✓ $service 运行中"
    else
        echo "  ✗ $service 未运行"
    fi
done
echo ""

# 检查端口
echo "2. 端口监听："
for port in 5432 6379 80 8686; do
    if ss -tlnp | grep -q ":$port "; then
        echo "  ✓ 端口 $port 正在监听"
    else
        echo "  ✗ 端口 $port 未监听"
    fi
done
echo ""

# 检查数据库连接
echo "3. 数据库连接："
cd /opt/openfi
source venv/bin/activate
if python scripts/test_db_connection.py &> /dev/null; then
    echo "  ✓ 数据库连接正常"
else
    echo "  ✗ 数据库连接失败"
fi
echo ""

# 检查 HTTP 服务
echo "4. HTTP 服务："
if curl -s -f http://localhost:8686/health &> /dev/null; then
    echo "  ✓ 后端服务响应正常"
else
    echo "  ✗ 后端服务无响应"
fi

if curl -s -f http://localhost/health &> /dev/null; then
    echo "  ✓ Nginx 代理正常"
else
    echo "  ✗ Nginx 代理失败"
fi
echo ""

echo "=== 检查完成 ==="
```

## 日志查看命令

```bash
# OpenFi 应用日志
journalctl -u openfi -f

# 查看最近的错误
journalctl -u openfi -p err -n 50

# Nginx 日志
tail -f /var/log/nginx/error.log
tail -f /var/log/nginx/access.log

# PostgreSQL 日志
tail -f /var/lib/pgsql/data/log/postgresql-*.log

# Redis 日志
tail -f /var/log/redis/redis.log
```

## 完全重置系统

如果所有方法都失败，可以完全重置系统：

```bash
# ⚠️ 警告：这会删除所有数据和配置

# 1. 停止所有服务
systemctl stop openfi nginx

# 2. 删除数据库
sudo -u postgres psql -c "DROP DATABASE IF EXISTS openfi;"
sudo -u postgres psql -c "DROP USER IF EXISTS openfi;"

# 3. 删除应用目录
rm -rf /opt/openfi

# 4. 重新运行部署脚本
bash quick_deploy.sh
```

## 获取帮助

如果以上方法都无法解决问题，请：

1. 收集日志信息：
```bash
# 创建诊断报告
mkdir -p /tmp/openfi-diagnostics
journalctl -u openfi -n 200 > /tmp/openfi-diagnostics/openfi.log
journalctl -u nginx -n 100 > /tmp/openfi-diagnostics/nginx.log
journalctl -u postgresql -n 100 > /tmp/openfi-diagnostics/postgresql.log
systemctl status openfi > /tmp/openfi-diagnostics/status.txt
cat /opt/openfi/.env > /tmp/openfi-diagnostics/env.txt
tar -czf openfi-diagnostics.tar.gz -C /tmp openfi-diagnostics/
```

2. 在 GitHub 上提交 Issue，附上诊断报告
3. 访问项目文档获取更多信息

## 预防措施

1. **定期备份数据库**
```bash
cd /opt/openfi
source venv/bin/activate
python scripts/backup_cli.py create
```

2. **监控服务状态**
```bash
# 设置定时任务检查服务
crontab -e
# 添加：
# */5 * * * * systemctl is-active openfi || systemctl restart openfi
```

3. **保持系统更新**
```bash
cd /opt/openfi
git pull origin main
source venv/bin/activate
pip install -r requirements.txt --upgrade
systemctl restart openfi
```
