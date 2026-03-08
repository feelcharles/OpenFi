#!/bin/bash

# ============================================================================
# System Dependencies Check Script
# 系统依赖检查脚本
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "OpenFi - System Dependencies Check"
echo "OpenFi - 系统依赖检查"
echo "=========================================="
echo ""

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "OS: $NAME $VERSION_ID"
    OS_ID=$ID
else
    echo -e "${RED}Cannot detect OS${NC}"
    exit 1
fi

echo ""
echo "Checking required dependencies..."
echo "检查必需依赖..."
echo ""

MISSING_DEPS=()

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓${NC} Python 3: $PYTHON_VERSION"
else
    echo -e "${RED}✗${NC} Python 3: Not found"
    MISSING_DEPS+=("python3")
fi

# Check pip
if command -v pip3 &> /dev/null; then
    PIP_VERSION=$(pip3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓${NC} pip: $PIP_VERSION"
else
    echo -e "${RED}✗${NC} pip: Not found"
    MISSING_DEPS+=("python3-pip")
fi

# Check git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    echo -e "${GREEN}✓${NC} git: $GIT_VERSION"
else
    echo -e "${RED}✗${NC} git: Not found"
    MISSING_DEPS+=("git")
fi

# Check PostgreSQL client
if command -v psql &> /dev/null; then
    PSQL_VERSION=$(psql --version | cut -d' ' -f3)
    echo -e "${GREEN}✓${NC} PostgreSQL client: $PSQL_VERSION"
else
    echo -e "${YELLOW}⚠${NC} PostgreSQL client: Not found (optional for local dev)"
fi

# Check Redis client
if command -v redis-cli &> /dev/null; then
    REDIS_VERSION=$(redis-cli --version | cut -d' ' -f2)
    echo -e "${GREEN}✓${NC} Redis client: $REDIS_VERSION"
else
    echo -e "${YELLOW}⚠${NC} Redis client: Not found (optional for local dev)"
fi

# Check development libraries
echo ""
echo "Checking development libraries..."
echo "检查开发库..."
echo ""

# Check for PostgreSQL dev libraries
if [ "$OS_ID" = "ubuntu" ] || [ "$OS_ID" = "debian" ]; then
    if dpkg -l | grep -q libpq-dev; then
        echo -e "${GREEN}✓${NC} PostgreSQL dev libraries"
    else
        echo -e "${YELLOW}⚠${NC} PostgreSQL dev libraries: Not found"
        MISSING_DEPS+=("libpq-dev")
    fi
    
    if dpkg -l | grep -q libssl-dev; then
        echo -e "${GREEN}✓${NC} OpenSSL dev libraries"
    else
        echo -e "${YELLOW}⚠${NC} OpenSSL dev libraries: Not found"
        MISSING_DEPS+=("libssl-dev")
    fi
    
    if dpkg -l | grep -q libxml2-dev; then
        echo -e "${GREEN}✓${NC} libxml2 dev libraries"
    else
        echo -e "${YELLOW}⚠${NC} libxml2 dev libraries: Not found"
        MISSING_DEPS+=("libxml2-dev libxslt1-dev")
    fi
elif [ "$OS_ID" = "centos" ] || [ "$OS_ID" = "rhel" ] || [ "$OS_ID" = "fedora" ]; then
    if rpm -q postgresql-devel &> /dev/null; then
        echo -e "${GREEN}✓${NC} PostgreSQL dev libraries"
    else
        echo -e "${YELLOW}⚠${NC} PostgreSQL dev libraries: Not found"
        MISSING_DEPS+=("postgresql-devel")
    fi
    
    if rpm -q openssl-devel &> /dev/null; then
        echo -e "${GREEN}✓${NC} OpenSSL dev libraries"
    else
        echo -e "${YELLOW}⚠${NC} OpenSSL dev libraries: Not found"
        MISSING_DEPS+=("openssl-devel")
    fi
    
    if rpm -q libxml2-devel &> /dev/null; then
        echo -e "${GREEN}✓${NC} libxml2 dev libraries"
    else
        echo -e "${YELLOW}⚠${NC} libxml2 dev libraries: Not found"
        MISSING_DEPS+=("libxml2-devel libxslt-devel")
    fi
fi

echo ""
echo "=========================================="

if [ ${#MISSING_DEPS[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ All dependencies are installed!${NC}"
    echo -e "${GREEN}✓ 所有依赖已安装！${NC}"
else
    echo -e "${YELLOW}⚠ Missing dependencies:${NC}"
    echo -e "${YELLOW}⚠ 缺少依赖：${NC}"
    echo ""
    
    if [ "$OS_ID" = "ubuntu" ] || [ "$OS_ID" = "debian" ]; then
        echo "Install with / 安装命令:"
        echo "  sudo apt-get install -y ${MISSING_DEPS[*]}"
    elif [ "$OS_ID" = "centos" ] || [ "$OS_ID" = "rhel" ]; then
        echo "Install with / 安装命令:"
        echo "  sudo yum install -y ${MISSING_DEPS[*]}"
    elif [ "$OS_ID" = "fedora" ]; then
        echo "Install with / 安装命令:"
        echo "  sudo dnf install -y ${MISSING_DEPS[*]}"
    fi
fi

echo "=========================================="
