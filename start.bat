@echo off
REM ============================================================================
REM OpenFi 一键启动脚本 (Windows)
REM One-Click Start Script for OpenFi (Windows)
REM ============================================================================

echo ========================================
echo OpenFi 一键启动 / One-Click Start
echo ========================================
echo.

REM 检查 Docker 是否运行
echo [1/4] 检查 Docker 服务...
echo [1/4] Checking Docker service...
docker info >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop
    echo [ERROR] Docker is not running, please start Docker Desktop first
    pause
    exit /b 1
)
echo [成功] Docker 运行正常
echo [SUCCESS] Docker is running
echo.

REM 启动 PostgreSQL 和 Redis
echo [2/4] 启动数据库服务 (PostgreSQL + Redis)...
echo [2/4] Starting database services (PostgreSQL + Redis)...
docker-compose up -d postgres redis

if errorlevel 1 (
    echo [错误] 数据库服务启动失败
    echo [ERROR] Failed to start database services
    pause
    exit /b 1
)

echo [成功] 数据库服务启动成功
echo [SUCCESS] Database services started
echo.

REM 等待服务就绪
echo [3/4] 等待服务就绪...
echo [3/4] Waiting for services to be ready...
timeout /t 10 /nobreak >nul

REM 启动 OpenFi Web 服务器
echo [4/4] 启动 OpenFi Web 服务器...
echo [4/4] Starting OpenFi Web Server...
echo.

REM 检查端口 8686 是否被占用
netstat -ano | findstr :8686 >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口 8686 已被占用
    echo [WARNING] Port 8686 is already in use
    echo.
    echo 如果 OpenFi 已在运行，请访问: http://localhost:8686
    echo If OpenFi is already running, please visit: http://localhost:8686
    echo.
    pause
    exit /b 0
)

echo 启动中... 请稍候...
echo Starting... Please wait...
echo.

start "OpenFi Server" cmd /k "python -m uvicorn system_core.web_backend.app:app --host 0.0.0.0 --port 8686"

REM 等待服务器启动
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo 🎉 OpenFi 启动成功！
echo 🎉 OpenFi Started Successfully!
echo ========================================
echo.
echo 访问地址 / Access URLs:
echo   主应用 / Main App:  http://localhost:8686/app
echo   API 文档 / API Docs: http://localhost:8686/docs
echo   健康检查 / Health:   http://localhost:8686/health
echo.
echo 默认账户 / Default Account:
echo   用户名 / Username: admin
echo   密码 / Password:   admin123
echo   ⚠️  首次登录必须修改密码
echo   ⚠️  Must change password on first login
echo.
echo 服务状态 / Service Status:
docker-compose ps
echo.
echo 管理命令 / Management Commands:
echo   停止服务器 / Stop:    Ctrl+C (在服务器窗口中)
echo   查看日志 / Logs:      docker-compose logs -f
echo   停止所有 / Stop All:  docker-compose down
echo.
echo ========================================
echo.
pause
