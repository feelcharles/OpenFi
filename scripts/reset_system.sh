#!/bin/bash

#==============================================================================
# OpenFi 系统重置脚本
# 警告: 此脚本将删除所有数据，包括数据库、配置文件和日志
# 需要管理员密码验证和二次确认
#==============================================================================

set -e

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

# 验证管理员密码
verify_admin_password() {
    log_warning "=========================================="
    log_warning "⚠️  系统重置操作"
    log_warning "=========================================="
    echo ""
    log_warning "此操作将:"
    echo "  1. 停止所有OpenFi服务"
    echo "  2. 删除PostgreSQL数据库"
    echo "  3. 清空Redis缓存"
    echo "  4. 删除所有日志文件"
    echo "  5. 删除配置文件和密钥"
    echo "  6. 删除备份文件"
    echo ""
    log_error "⚠️  所有数据将被永久删除，无法恢复！"
    echo ""
    
    # 第一次确认
    read -p "是否继续? 请输入 'YES' (大写) 确认: " CONFIRM1
    
    if [[ "$CONFIRM1" != "YES" ]]; then
        log_info "操作已取消"
        exit 0
    fi
    
    echo ""
    log_warning "请再次确认..."
    
    # 第二次确认
    read -p "确定要重置整个系统吗? 请输入 'RESET' (大写) 确认: " CONFIRM2
    
    if [[ "$CONFIRM2" != "RESET" ]]; then
        log_info "操作已取消"
        exit 0
    fi
    
    echo ""
    log_warning "最后确认: 请输入当前系统管理员密码"
    
    # 验证sudo密码
    if ! sudo -v; then
        log_error "密码验证失败"
        exit 1
    fi
    
    log_success "验证通过，开始重置系统..."
    echo ""
}

# 停止服务
stop_services() {
    log_info "停止OpenFi服务..."
    
    systemctl stop openfi 2>/dev/null || true
    systemctl stop nginx 2>/dev/null || true
    
    log_success "服务已停止"
}

# 删除数据库
drop_database() {
    log_info "删除PostgreSQL数据库..."
    
    # 断开所有连接
    sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'openfi';" 2>/dev/null || true
    
    # 删除数据库
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS openfi;" 2>/dev/null || true
    
    # 删除用户
    sudo -u postgres psql -c "DROP USER IF EXISTS openfi;" 2>/dev/null || true
    
    log_success "数据库已删除"
}

# 清空Redis
flush_redis() {
    log_info "清空Redis缓存..."
    
    if command -v redis-cli &> /dev/null; then
        redis-cli FLUSHALL 2>/dev/null || true
        log_success "Redis缓存已清空"
    else
        log_warning "Redis CLI未找到，跳过"
    fi
}

# 删除文件
remove_files() {
    log_info "删除文件..."
    
    cd /opt/openfi
    
    # 删除日志
    if [[ -d logs ]]; then
        rm -rf logs/*
        log_info "✓ 日志文件已删除"
    fi
    
    # 删除备份
    if [[ -d backups ]]; then
        rm -rf backups/*
        log_info "✓ 备份文件已删除"
    fi
    
    # 删除EA日志
    if [[ -d ea/logs ]]; then
        rm -rf ea/logs/*
        log_info "✓ EA日志已删除"
    fi
    
    # 删除环境变量文件
    if [[ -f .env ]]; then
        rm -f .env
        log_info "✓ 环境变量文件已删除"
    fi
    
    # 删除JWT密钥
    if [[ -d config/keys ]]; then
        rm -f config/keys/jwt_private.pem
        rm -f config/keys/jwt_public.pem
        log_info "✓ JWT密钥已删除"
    fi
    
    # 删除Python缓存
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    log_info "✓ Python缓存已清理"
    
    log_success "文件删除完成"
}

# 重置Alembic迁移历史
reset_alembic() {
    log_info "重置Alembic迁移历史..."
    
    cd /opt/openfi
    
    if [[ -d alembic/versions ]]; then
        # 保留迁移文件，但删除alembic_version表记录
        log_info "迁移文件保留，数据库表记录已随数据库删除"
    fi
    
    log_success "Alembic重置完成"
}

# 显示重置结果
show_reset_info() {
    echo ""
    echo "========================================"
    log_success "系统重置完成！"
    echo "========================================"
    echo ""
    echo "已完成的操作:"
    echo "  ✓ 停止所有服务"
    echo "  ✓ 删除数据库和用户"
    echo "  ✓ 清空Redis缓存"
    echo "  ✓ 删除日志和备份文件"
    echo "  ✓ 删除配置文件和密钥"
    echo "  ✓ 清理Python缓存"
    echo ""
    echo "下一步操作:"
    echo ""
    echo "重新部署系统:"
    echo "  bash /opt/openfi/quick_deploy.sh"
    echo ""
    echo "或者手动配置:"
    echo "  1. 创建数据库: sudo -u postgres psql -c \"CREATE DATABASE openfi;\""
    echo "  2. 配置环境变量: cp /opt/openfi/.env.example /opt/openfi/.env"
    echo "  3. 运行数据库迁移: cd /opt/openfi && source venv/bin/activate && alembic upgrade head"
    echo "  4. 启动服务: systemctl start openfi"
    echo ""
    echo "========================================"
}

# 主函数
main() {
    check_root
    verify_admin_password
    
    # 开始倒计时
    log_warning "5秒后开始重置，按Ctrl+C取消..."
    for i in {5..1}; do
        echo -n "$i... "
        sleep 1
    done
    echo ""
    echo ""
    
    stop_services
    drop_database
    flush_redis
    remove_files
    reset_alembic
    show_reset_info
}

# 运行主函数
main
