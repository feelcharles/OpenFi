#!/bin/bash

#==============================================================================
# OpenFi 一键部署脚本 v5.0
# 支持: CentOS 7/8, RHEL 7/8, Ubuntu 18.04+, Debian 9+, Alibaba Cloud Linux
# 最低要求: Python 3.11+
# 更新: 完善错误处理、服务验证、健康检查
#==============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否为root用户
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "此脚本必须以root用户运行"
        log_info "请使用: sudo bash $0"
        exit 1
    fi
}

# 检测操作系统
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    else
        log_error "无法检测操作系统"
        exit 1
    fi
    
    log_info "检测到操作系统: $OS $OS_VERSION"
}

# 检测包管理器
detect_package_manager() {
    if command -v dnf &> /dev/null; then
        PKG_MANAGER="dnf"
    elif command -v yum &> /dev/null; then
        PKG_MANAGER="yum"
    elif command -v apt-get &> /dev/null; then
        PKG_MANAGER="apt-get"
    else
        log_error "未找到支持的包管理器"
        exit 1
    fi
    
    log_info "使用包管理器: $PKG_MANAGER"
}

# 检查Python版本
check_python_version() {
    log_info "检查Python版本..."
    
    for py_cmd in python3.13 python3.12 python3.11 python3; do
        if command -v $py_cmd &> /dev/null; then
            PY_VERSION=$($py_cmd --version 2>&1 | awk '{print $2}')
            PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
            PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)
            
            if [[ $PY_MAJOR -eq 3 ]] && [[ $PY_MINOR -ge 11 ]]; then
                PYTHON_CMD=$py_cmd
                log_success "找到Python $PY_VERSION"
                return 0
            fi
        fi
    done
    
    log_warning "未找到Python 3.11+，尝试安装..."
    install_python311
}

# 安装Python 3.11+
install_python311() {
    log_info "安装Python 3.11+..."
    
    if [[ "$PKG_MANAGER" == "yum" ]] || [[ "$PKG_MANAGER" == "dnf" ]]; then
        # CentOS/RHEL/Alibaba Cloud Linux
        
        # 检测所有EPEL变体
        EPEL_INSTALLED=false
        for epel_pkg in epel-release epel-aliyuncs-release epel-tencent-release; do
            if rpm -q $epel_pkg &> /dev/null; then
                EPEL_INSTALLED=true
                log_info "检测到EPEL变体: $epel_pkg"
                break
            fi
        done
        
        # 如果没有EPEL，尝试安装（使用--allowerasing解决冲突）
        if ! $EPEL_INSTALLED; then
            log_info "安装EPEL仓库..."
            $PKG_MANAGER install -y --allowerasing epel-release 2>/dev/null || \
            $PKG_MANAGER install -y --skip-broken epel-release 2>/dev/null || \
            log_warning "EPEL安装失败，尝试直接安装Python"
        fi
        
        # 尝试安装Python 3.11+（多种策略）
        if $PKG_MANAGER install -y python3.11 python3.11-devel python3.11-pip 2>/dev/null; then
            log_info "Python 3.11从标准仓库安装成功"
        elif $PKG_MANAGER install -y --skip-broken python3.11 python3.11-devel 2>/dev/null; then
            log_info "Python 3.11使用--skip-broken安装成功"
        elif $PKG_MANAGER install -y --nobest python3.11 python3.11-devel 2>/dev/null; then
            log_info "Python 3.11使用--nobest安装成功"
        else
            log_warning "无法从仓库安装Python 3.11，从源码编译..."
            install_python_from_source
            return
        fi
        
        # 验证安装
        if command -v python3.11 &> /dev/null; then
            PYTHON_CMD="python3.11"
        else
            log_error "Python 3.11安装失败"
            install_python_from_source
            return
        fi
        
    elif [[ "$PKG_MANAGER" == "apt-get" ]]; then
        # Ubuntu/Debian
        apt-get update
        apt-get install -y software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
        apt-get update
        apt-get install -y python3.11 python3.11-dev python3.11-venv python3-pip
        
        if command -v python3.11 &> /dev/null; then
            PYTHON_CMD="python3.11"
        else
            log_error "Python 3.11安装失败"
            exit 1
        fi
    fi
    
    PY_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    log_success "Python $PY_VERSION 安装成功"
}

# 从源码安装Python（备用方案）
install_python_from_source() {
    log_info "从源码编译Python 3.11..."
    
    # 安装编译依赖
    if [[ "$PKG_MANAGER" == "yum" ]] || [[ "$PKG_MANAGER" == "dnf" ]]; then
        $PKG_MANAGER install -y gcc gcc-c++ make openssl-devel bzip2-devel libffi-devel zlib-devel wget sqlite-devel readline-devel xz-devel
    elif [[ "$PKG_MANAGER" == "apt-get" ]]; then
        apt-get install -y build-essential libssl-dev libbz2-dev libffi-dev zlib1g-dev wget libsqlite3-dev libreadline-dev liblzma-dev
    fi
    
    cd /tmp
    if [[ -f Python-3.11.8.tgz ]]; then
        rm -f Python-3.11.8.tgz
    fi
    
    wget --timeout=30 --tries=3 https://www.python.org/ftp/python/3.11.8/Python-3.11.8.tgz || {
        log_error "下载Python源码失败"
        exit 1
    }
    
    tar xzf Python-3.11.8.tgz
    cd Python-3.11.8
    ./configure --enable-optimizations --prefix=/usr/local --with-ensurepip=install
    make -j$(nproc) || make
    make altinstall
    
    # 创建符号链接
    ln -sf /usr/local/bin/python3.11 /usr/bin/python3.11
    ln -sf /usr/local/bin/pip3.11 /usr/bin/pip3.11
    
    # 验证安装
    if command -v python3.11 &> /dev/null; then
        PYTHON_CMD="python3.11"
        log_success "Python 3.11 从源码安装成功"
    else
        log_error "Python 3.11源码编译失败"
        exit 1
    fi
}

# 安装系统依赖
install_system_dependencies() {
    log_info "安装系统依赖..."
    
    if [[ "$PKG_MANAGER" == "yum" ]] || [[ "$PKG_MANAGER" == "dnf" ]]; then
        $PKG_MANAGER install -y git gcc gcc-c++ make openssl-devel libxml2-devel libxslt-devel redis nginx || {
            log_error "系统依赖安装失败"
            exit 1
        }
        
        # 启动Redis
        systemctl enable redis 2>/dev/null || systemctl enable redis-server 2>/dev/null
        systemctl start redis 2>/dev/null || systemctl start redis-server 2>/dev/null
        
    elif [[ "$PKG_MANAGER" == "apt-get" ]]; then
        apt-get update
        apt-get install -y git build-essential libssl-dev libxml2-dev libxslt1-dev redis-server nginx || {
            log_error "系统依赖安装失败"
            exit 1
        }
        
        # 启动Redis
        systemctl enable redis-server
        systemctl start redis-server
    fi
    
    # 验证Redis
    sleep 2
    if systemctl is-active redis &> /dev/null || systemctl is-active redis-server &> /dev/null; then
        log_success "Redis服务运行正常"
    else
        log_warning "Redis服务未运行，尝试启动..."
        systemctl start redis 2>/dev/null || systemctl start redis-server 2>/dev/null || true
    fi
    
    log_success "系统依赖安装完成"
}

# 安装PostgreSQL
install_postgresql() {
    log_info "检查PostgreSQL..."
    
    if command -v psql &> /dev/null; then
        log_success "PostgreSQL已安装"
        systemctl start postgresql 2>/dev/null || service postgresql start 2>/dev/null || true
        
        # 等待PostgreSQL启动
        wait_for_postgresql
        return 0
    fi
    
    log_info "安装PostgreSQL..."
    
    if [[ "$PKG_MANAGER" == "yum" ]] || [[ "$PKG_MANAGER" == "dnf" ]]; then
        $PKG_MANAGER install -y postgresql-server postgresql-contrib || {
            log_error "PostgreSQL安装失败"
            exit 1
        }
        
        # 初始化数据库（尝试多种方法）
        if [[ ! -d /var/lib/pgsql/data/base ]]; then
            log_info "初始化PostgreSQL数据库..."
            postgresql-setup --initdb 2>/dev/null || \
            postgresql-setup initdb 2>/dev/null || \
            /usr/bin/postgresql-setup initdb 2>/dev/null || \
            /usr/pgsql-*/bin/postgresql-*-setup initdb 2>/dev/null || {
                log_error "PostgreSQL初始化失败"
                exit 1
            }
        fi
        
        systemctl enable postgresql
        systemctl start postgresql
        
    elif [[ "$PKG_MANAGER" == "apt-get" ]]; then
        apt-get install -y postgresql postgresql-contrib || {
            log_error "PostgreSQL安装失败"
            exit 1
        }
        systemctl enable postgresql
        systemctl start postgresql
    fi
    
    # 等待PostgreSQL完全启动
    wait_for_postgresql
    
    log_success "PostgreSQL安装完成"
}

# 等待PostgreSQL启动
wait_for_postgresql() {
    log_info "等待PostgreSQL启动..."
    
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if sudo -u postgres pg_isready &> /dev/null; then
            log_success "PostgreSQL已就绪"
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 1
    done
    
    log_error "PostgreSQL启动超时"
    exit 1
}

# 配置PostgreSQL
configure_postgresql() {
    log_info "配置PostgreSQL..."
    
    # 生成随机密码（只包含字母和数字）- 使用全局变量
    export DB_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 20)
    
    log_info "创建数据库和用户..."
    # 创建数据库和用户
    sudo -u postgres psql -c "CREATE DATABASE openfi;" 2>/dev/null || log_warning "数据库openfi可能已存在"
    sudo -u postgres psql -c "CREATE USER openfi WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || log_warning "用户openfi可能已存在"
    sudo -u postgres psql -c "ALTER USER openfi WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || true
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE openfi TO openfi;"
    sudo -u postgres psql -d openfi -c "GRANT ALL ON SCHEMA public TO openfi;" 2>/dev/null || true
    sudo -u postgres psql -d openfi -c "ALTER DATABASE openfi OWNER TO openfi;" 2>/dev/null || true
    
    # 配置pg_hba.conf允许密码认证
    log_info "配置pg_hba.conf..."
    PG_HBA=$(sudo -u postgres psql -t -P format=unaligned -c 'SHOW hba_file;' 2>/dev/null)
    
    if [[ -z "$PG_HBA" ]] || [[ ! -f "$PG_HBA" ]]; then
        log_error "无法找到pg_hba.conf文件"
        exit 1
    fi
    
    # 备份原文件
    cp "$PG_HBA" "${PG_HBA}.backup.$(date +%Y%m%d%H%M%S)" 2>/dev/null || true
    
    # 移除旧的openfi规则
    sed -i '/# OpenFi database access/d' "$PG_HBA"
    sed -i '/host.*openfi.*openfi/d' "$PG_HBA"
    
    # 创建临时文件，在开头插入新规则
    cat > /tmp/pg_hba_openfi.tmp << 'HBAEOF'
# OpenFi database access
host    openfi          openfi          127.0.0.1/32            md5
host    openfi          openfi          ::1/128                 md5

HBAEOF
    
    # 合并文件
    cat "$PG_HBA" >> /tmp/pg_hba_openfi.tmp
    mv /tmp/pg_hba_openfi.tmp "$PG_HBA"
    chown postgres:postgres "$PG_HBA" 2>/dev/null || true
    chmod 600 "$PG_HBA" 2>/dev/null || true
    
    log_info "重启PostgreSQL服务..."
    systemctl restart postgresql 2>/dev/null || service postgresql restart 2>/dev/null
    
    # 等待PostgreSQL重启
    wait_for_postgresql
    
    # 验证数据库连接
    log_info "验证数据库连接..."
    local max_attempts=5
    local attempt=0
    local connected=false
    
    while [ $attempt -lt $max_attempts ]; do
        if PGPASSWORD="$DB_PASSWORD" psql -h localhost -U openfi -d openfi -c "SELECT 1;" 2>&1 | grep -q "1 row"; then
            connected=true
            break
        fi
        attempt=$((attempt + 1))
        if [ $attempt -lt $max_attempts ]; then
            log_info "等待数据库配置生效... ($attempt/$max_attempts)"
            sleep 2
        fi
    done
    
    if $connected; then
        log_success "数据库连接验证成功"
    else
        log_error "数据库连接验证失败"
        log_info ""
        log_info "=== 诊断信息 ==="
        log_info "数据库密码: $DB_PASSWORD"
        log_info "pg_hba.conf: $PG_HBA"
        log_info ""
        log_info "=== PostgreSQL服务状态 ==="
        systemctl status postgresql --no-pager -l 2>&1 | head -n 20 || service postgresql status 2>&1 | head -n 20 || true
        log_info ""
        log_info "=== 尝试手动连接 ==="
        PGPASSWORD="$DB_PASSWORD" psql -h localhost -U openfi -d openfi -c "SELECT 1;" 2>&1 || true
        log_info ""
        log_info "=== pg_hba.conf前10行 ==="
        head -n 10 "$PG_HBA" 2>&1 || true
        log_info ""
        log_info "=== PostgreSQL进程 ==="
        ps aux | grep postgres | grep -v grep || true
        log_info ""
        log_info "=== 监听端口 ==="
        ss -tlnp | grep 5432 || netstat -tlnp | grep 5432 || true
        exit 1
    fi
    
    log_success "PostgreSQL配置完成"
}

# 克隆代码仓库
clone_repository() {
    log_info "克隆OpenFi代码仓库..."
    
    INSTALL_DIR="/opt/openfi"
    
    if [[ -d "$INSTALL_DIR" ]]; then
        log_warning "目录已存在，更新代码..."
        cd "$INSTALL_DIR"
        git pull || {
            log_warning "Git pull失败，继续使用现有代码"
        }
    else
        git clone https://github.com/feelcharles/OpenFi.git "$INSTALL_DIR" || {
            log_error "克隆代码仓库失败"
            exit 1
        }
        cd "$INSTALL_DIR"
    fi
    
    # 如果仓库中的部署脚本更新了，使用最新版本重新执行
    if [[ -f "$INSTALL_DIR/quick_deploy.sh" ]]; then
        REPO_SCRIPT="$INSTALL_DIR/quick_deploy.sh"
        CURRENT_SCRIPT="${BASH_SOURCE[0]}"
        
        # 比较脚本是否不同
        if ! cmp -s "$CURRENT_SCRIPT" "$REPO_SCRIPT"; then
            log_info "检测到部署脚本更新，使用最新版本..."
            cp "$REPO_SCRIPT" "$CURRENT_SCRIPT"
            log_info "重新执行更新后的脚本..."
            exec bash "$CURRENT_SCRIPT"
            exit 0
        fi
    fi
    
    log_success "代码仓库准备完成"
}

# 创建Python虚拟环境
create_virtualenv() {
    log_info "创建Python虚拟环境..."
    
    cd /opt/openfi
    
    # 确保有pip
    $PYTHON_CMD -m ensurepip 2>/dev/null || true
    $PYTHON_CMD -m pip install --upgrade pip 2>/dev/null || true
    
    # 创建虚拟环境
    if $PYTHON_CMD -m venv venv 2>/dev/null; then
        log_info "使用venv创建虚拟环境"
    else
        log_warning "venv不可用，尝试安装virtualenv..."
        $PYTHON_CMD -m pip install virtualenv || {
            log_error "无法创建虚拟环境"
            exit 1
        }
        $PYTHON_CMD -m virtualenv venv || {
            log_error "virtualenv创建失败"
            exit 1
        }
    fi
    
    # 激活并安装依赖
    source venv/bin/activate
    
    # 配置pip超时
    pip config set global.timeout 120 2>/dev/null || true
    
    pip install --upgrade pip
    
    log_info "安装Python依赖包..."
    if ! pip install -r requirements.txt; then
        log_error "依赖安装失败"
        log_info "尝试使用国内镜像源重新安装..."
        pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ 2>/dev/null || true
        pip install -r requirements.txt || {
            log_error "依赖安装失败，请检查requirements.txt"
            exit 1
        }
    fi
    
    log_success "虚拟环境创建完成"
}

# 配置环境变量
configure_environment() {
    log_info "配置环境变量..."
    
    cd /opt/openfi
    
    # 生成密钥
    SECRET_KEY=$(openssl rand -hex 32)
    ENCRYPTION_KEY=$(openssl rand -base64 32 | head -c 32)
    
    cat > .env << EOF
# Application
APP_NAME=OpenFi
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Database
DB_USER=openfi
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=localhost
DB_PORT=5432
DB_NAME=openfi
DATABASE_POOL_MIN=5
DATABASE_POOL_MAX=20

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=${SECRET_KEY}
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
ENCRYPTION_KEY=${ENCRYPTION_KEY}

# Monitoring
PROMETHEUS_PORT=9090

# Logging
LOG_FILE_PATH=logs/openfi.log
LOG_MAX_BYTES=104857600
LOG_BACKUP_COUNT=10
LOG_RETENTION_DAYS=30

# Vector Database (optional)
VECTOR_DB_PROVIDER=pinecone

# External APIs (optional - configure later)
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# TELEGRAM_BOT_TOKEN=
# DISCORD_BOT_TOKEN=
EOF
    
    chmod 600 .env
    log_success "环境变量配置完成"
}

# 初始化数据库
initialize_database() {
    log_info "初始化数据库..."
    
    cd /opt/openfi
    source venv/bin/activate
    
    # 运行数据库迁移
    log_info "运行数据库迁移..."
    if ! alembic upgrade head; then
        log_error "数据库迁移失败"
        log_info "查看详细错误信息，请运行: cd /opt/openfi && source venv/bin/activate && alembic upgrade head"
        exit 1
    fi
    log_success "数据库迁移完成"
    
    # 创建默认管理员账户
    log_info "创建默认管理员账户..."
    /opt/openfi/venv/bin/python << 'PYEOF'
import sys
sys.path.insert(0, '/opt/openfi')

try:
    from system_core.database.client import get_db_session
    from system_core.database.models import User
    from system_core.auth.password import hash_password
    from datetime import datetime

    session = next(get_db_session())

    # 检查是否已存在admin用户
    existing_admin = session.query(User).filter_by(username='admin').first()

    if not existing_admin:
        admin_user = User(
            username='admin',
            email='admin@openfi.local',
            password_hash=hash_password('admin123'),
            role='admin',
            is_active=True,
            must_change_password=True,
            created_at=datetime.utcnow()
        )
        session.add(admin_user)
        session.commit()
        print("默认管理员账户创建成功")
    else:
        print("管理员账户已存在")

    session.close()
except Exception as e:
    print(f"创建管理员账户失败: {e}")
    sys.exit(1)
PYEOF
    
    if [ $? -ne 0 ]; then
        log_error "管理员账户创建失败"
        exit 1
    fi
    
    log_success "数据库初始化完成"
}

# 配置systemd服务
configure_systemd() {
    log_info "配置systemd服务..."
    
    # 检查8686端口是否被占用
    if ss -tlnp | grep -q ":8686 " || netstat -tlnp 2>/dev/null | grep -q ":8686 "; then
        log_warning "端口8686已被占用"
        if systemctl is-active openfi &> /dev/null; then
            log_info "OpenFi服务正在运行，将重启"
            systemctl stop openfi
            sleep 2
        else
            log_error "端口8686被其他服务占用"
            log_info "查看占用进程: ss -tlnp | grep :8686"
            exit 1
        fi
    fi
    
    # 测试应用是否能正常导入
    log_info "测试应用配置..."
    cd /opt/openfi
    source venv/bin/activate
    
    if ! python -c "from system_core.web_backend.app import app; print('App import successful')" 2>/dev/null; then
        log_error "应用导入失败，检查依赖和配置"
        python -c "from system_core.web_backend.app import app" || true
        exit 1
    fi
    
    cat > /etc/systemd/system/openfi.service << 'EOF'
[Unit]
Description=OpenFi Trading Platform
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/openfi
Environment="PATH=/opt/openfi/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=/opt/openfi"
ExecStart=/opt/openfi/venv/bin/uvicorn system_core.web_backend.app:app --host 0.0.0.0 --port 8686 --log-level info
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable openfi
    
    log_info "启动OpenFi服务..."
    if ! systemctl start openfi; then
        log_error "OpenFi服务启动失败"
        journalctl -u openfi -n 50 --no-pager
        exit 1
    fi
    
    # 等待服务启动
    log_info "等待服务启动..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if systemctl is-active openfi &> /dev/null; then
            # 检查端口是否监听
            if ss -tlnp | grep -q ":8686 " || netstat -tlnp 2>/dev/null | grep -q ":8686 "; then
                log_success "OpenFi服务启动成功"
                return 0
            fi
        fi
        
        attempt=$((attempt + 1))
        sleep 1
    done
    
    log_error "OpenFi服务启动超时"
    journalctl -u openfi -n 50 --no-pager
    exit 1
}

# 配置Nginx
configure_nginx() {
    log_info "配置Nginx..."
    
    # 检测Nginx配置目录
    if [[ -d /etc/nginx/sites-available ]]; then
        # Ubuntu/Debian
        NGINX_CONF="/etc/nginx/sites-available/openfi"
        NGINX_ENABLED="/etc/nginx/sites-enabled/openfi"
    else
        # CentOS/RHEL
        NGINX_CONF="/etc/nginx/conf.d/openfi.conf"
    fi
    
    # 检查80端口是否被占用
    if ss -tlnp | grep -q ":80 " || netstat -tlnp 2>/dev/null | grep -q ":80 "; then
        log_warning "端口80已被占用"
        if systemctl is-active nginx &> /dev/null; then
            log_info "Nginx正在运行，将重新配置"
        else
            log_error "端口80被其他服务占用，请先释放端口"
            log_info "查看占用进程: ss -tlnp | grep :80"
            exit 1
        fi
    fi
    
    # 写入配置文件
    cat > "$NGINX_CONF" << 'EOF'
server {
    listen 80;
    server_name _;
    
    client_max_body_size 100M;
    
    # 根路径和应用路径
    location / {
        proxy_pass http://127.0.0.1:8686;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # 缓冲设置
        proxy_buffering off;
        proxy_request_buffering off;
    }
    
    # 静态文件缓存
    location /static/ {
        proxy_pass http://127.0.0.1:8686/static/;
        proxy_cache_valid 200 1h;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
    
    # API路径不缓存
    location /api/ {
        proxy_pass http://127.0.0.1:8686/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }
    
    # WebSocket路径
    location /ws/ {
        proxy_pass http://127.0.0.1:8686/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
}
EOF
    
    # Ubuntu/Debian需要创建符号链接
    if [[ -d /etc/nginx/sites-available ]]; then
        ln -sf "$NGINX_CONF" "$NGINX_ENABLED" 2>/dev/null || true
    fi
    
    # 测试配置
    if ! nginx -t; then
        log_error "Nginx配置测试失败"
        cat "$NGINX_CONF"
        exit 1
    fi
    
    # 配置SELinux（如果启用）
    if command -v getenforce &> /dev/null && [[ "$(getenforce)" == "Enforcing" ]]; then
        log_info "配置SELinux允许Nginx代理..."
        setsebool -P httpd_can_network_connect 1 2>/dev/null || log_warning "SELinux配置失败，可能需要手动配置"
    fi
    
    systemctl enable nginx
    systemctl restart nginx
    
    # 验证Nginx启动
    sleep 2
    if ! systemctl is-active nginx &> /dev/null; then
        log_error "Nginx启动失败"
        journalctl -u nginx -n 20 --no-pager
        exit 1
    fi
    
    # 验证80端口监听
    if ss -tlnp | grep -q ":80 " || netstat -tlnp 2>/dev/null | grep -q ":80 "; then
        log_success "Nginx配置完成并正在监听80端口"
    else
        log_error "Nginx未监听80端口"
        exit 1
    fi
}

# 配置防火墙
configure_firewall() {
    log_info "配置防火墙..."
    
    if command -v firewall-cmd &> /dev/null; then
        firewall-cmd --permanent --add-port=80/tcp 2>/dev/null || true
        firewall-cmd --permanent --add-port=8686/tcp 2>/dev/null || true
        firewall-cmd --reload 2>/dev/null || true
    elif command -v ufw &> /dev/null; then
        ufw allow 80/tcp 2>/dev/null || true
        ufw allow 8686/tcp 2>/dev/null || true
    fi
    
    log_success "防火墙配置完成"
}

# 显示部署信息
show_deployment_info() {
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    # 最终健康检查
    log_info "执行最终健康检查..."
    
    local all_healthy=true
    
    # 检查PostgreSQL
    if systemctl is-active postgresql &> /dev/null && sudo -u postgres pg_isready &> /dev/null; then
        log_success "✓ PostgreSQL运行正常"
    else
        log_error "✗ PostgreSQL未运行"
        all_healthy=false
    fi
    
    # 检查Redis
    if systemctl is-active redis &> /dev/null || systemctl is-active redis-server &> /dev/null; then
        log_success "✓ Redis运行正常"
    else
        log_error "✗ Redis未运行"
        all_healthy=false
    fi
    
    # 检查Nginx
    if systemctl is-active nginx &> /dev/null; then
        log_success "✓ Nginx运行正常"
    else
        log_error "✗ Nginx未运行"
        all_healthy=false
    fi
    
    # 检查OpenFi
    if systemctl is-active openfi &> /dev/null; then
        log_success "✓ OpenFi服务运行正常"
    else
        log_error "✗ OpenFi服务未运行"
        all_healthy=false
    fi
    
    # HTTP健康检查
    log_info "测试HTTP访问..."
    sleep 5
    
    local http_ok=false
    local max_attempts=10
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        # 测试健康检查端点
        if curl -s -f http://localhost:8686/health &> /dev/null; then
            http_ok=true
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if $http_ok; then
        log_success "✓ HTTP服务响应正常"
        
        # 测试其他关键端点
        log_info "测试关键端点..."
        
        # 测试根路径
        if curl -s http://localhost:8686/ | grep -q "OpenFi\|service"; then
            log_success "✓ 根路径 (/) 正常"
        else
            log_warning "✗ 根路径响应异常"
        fi
        
        # 测试API文档
        if curl -s -f http://localhost:8686/docs &> /dev/null; then
            log_success "✓ API文档 (/docs) 可访问"
        else
            log_warning "✗ API文档不可访问"
        fi
        
        # 测试应用页面
        if curl -s -f http://localhost:8686/app &> /dev/null; then
            log_success "✓ 应用页面 (/app) 可访问"
        else
            log_warning "✗ 应用页面不可访问"
        fi
        
    else
        log_error "✗ HTTP服务响应超时"
        log_info "查看应用日志: journalctl -u openfi -n 50"
        all_healthy=false
    fi
    
    echo ""
    echo "========================================"
    if $all_healthy; then
        log_success "OpenFi 部署完成！"
    else
        log_warning "OpenFi 部署完成，但部分服务可能需要检查"
    fi
    echo "========================================"
    echo ""
    echo "访问地址:"
    echo "  http://$SERVER_IP"
    echo "  http://$SERVER_IP:8686"
    echo ""
    echo "默认账户:"
    echo "  用户名: admin"
    echo "  密码: admin123"
    echo "  ⚠️  首次登录必须修改密码"
    echo ""
    echo "服务管理:"
    echo "  查看状态: systemctl status openfi"
    echo "  查看日志: journalctl -u openfi -f"
    echo "  重启服务: systemctl restart openfi"
    echo ""
    echo "数据库信息:"
    echo "  数据库: openfi"
    echo "  用户: openfi"
    echo "  密码: $DB_PASSWORD"
    echo ""
    echo "配置文件:"
    echo "  /opt/openfi/.env"
    echo "  /opt/openfi/config/"
    echo ""
    echo "故障排查:"
    echo "  检查所有服务: systemctl status postgresql redis nginx openfi"
    echo "  查看OpenFi日志: journalctl -u openfi -n 100 --no-pager"
    echo "  查看Nginx日志: tail -f /var/log/nginx/error.log"
    echo "  测试后端连接: curl http://localhost:8686/health"
    echo "  测试Nginx代理: curl http://localhost/health"
    echo ""
    echo "常见问题:"
    echo "  404错误: 检查应用路由和静态文件"
    echo "  502错误: 检查OpenFi服务是否运行 (systemctl status openfi)"
    echo "  连接超时: 检查防火墙和SELinux设置"
    echo ""
    echo "========================================"
    echo ""
    log_success "🎉 部署完成！现在可以使用以下命令管理服务器："
    echo ""
    echo "📌 一键启动命令:"
    echo ""
    echo "  systemctl start openfi"
    echo ""
    echo "其他管理命令:"
    echo ""
    echo "  停止服务器:  systemctl stop openfi"
    echo "  重启服务器:  systemctl restart openfi"
    echo "  查看状态:    systemctl status openfi"
    echo "  查看日志:    journalctl -u openfi -f"
    echo ""
    echo "重置整个系统 (⚠️ 危险操作):"
    echo "  bash /opt/openfi/scripts/reset_system.sh"
    echo "  注意: 此操作将删除所有数据，需要输入管理员密码并二次确认"
    echo ""
    echo "========================================"
}

# 主函数
main() {
    echo "========================================"
    echo "OpenFi 一键部署脚本 v5.0"
    echo "========================================"
    echo ""
    
    check_root
    detect_os
    detect_package_manager
    check_python_version
    install_system_dependencies
    install_postgresql
    configure_postgresql
    clone_repository
    create_virtualenv
    configure_environment
    initialize_database
    configure_systemd
    configure_nginx
    configure_firewall
    show_deployment_info
}

# 运行主函数
main
