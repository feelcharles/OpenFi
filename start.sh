#!/bin/bash
# 启动 OpenFi 所需的服务

echo "正在启动 PostgreSQL 和 Redis 服务..."
echo "Starting PostgreSQL and Redis services..."

# 启动 Docker Compose 服务
docker-compose up -d postgres redis

echo ""
echo "等待服务启动..."
echo "Waiting for services to start..."
sleep 10

# 检查服务状态
echo ""
echo "检查服务状态..."
echo "Checking service status..."
docker-compose ps

echo ""
echo "服务已启动！"
echo "Services started!"
echo ""
echo "PostgreSQL: localhost:5432"
echo "Redis: localhost:6379"
echo ""
echo "运行测试: python test_all_system.py"
echo "Run tests: python test_all_system.py"
