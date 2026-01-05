#!/bin/bash
# ========================================
# QuickShare - Redis 安装脚本（WSL2）
# ========================================
# ⚠️  这是内部脚本，由 install_wsl2_redis.bat 自动调用
#     用户不应直接运行此脚本
# ========================================
# 此脚本在 WSL2 中安装和配置 Redis
# ========================================

set -e  # 遇到错误立即退出

echo "========================================"
echo "QuickShare - Redis 安装脚本（WSL2）"
echo "========================================"
echo ""

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  需要 root 权限，使用 sudo 运行..."
    exec sudo bash "$0" "$@"
fi

# ========================================
# 步骤 1: 更新系统包
# ========================================
echo "[1/5] 更新系统包列表..."
apt-get update -qq
echo "✓ 系统包列表已更新"
echo ""

# ========================================
# 步骤 2: 安装 Redis
# ========================================
echo "[2/5] 检查 Redis 是否已安装..."
if command -v redis-server &> /dev/null; then
    REDIS_VERSION=$(redis-server --version | awk '{print $3}' | cut -d'=' -f2)
    echo "✓ Redis 已安装，版本: $REDIS_VERSION"
    
    # 询问是否重新安装
    read -p "是否重新安装 Redis？(y/N): " REINSTALL
    if [[ ! "$REINSTALL" =~ ^[Yy]$ ]]; then
        echo "跳过 Redis 安装"
        INSTALL_REDIS=false
    else
        INSTALL_REDIS=true
    fi
else
    INSTALL_REDIS=true
fi

if [ "$INSTALL_REDIS" = true ]; then
    echo "正在安装 Redis..."
    apt-get install -y redis-server
    if [ $? -eq 0 ]; then
        echo "✓ Redis 安装成功"
    else
        echo "❌ Redis 安装失败"
        exit 1
    fi
fi
echo ""

# ========================================
# 步骤 3: 配置 Redis
# ========================================
echo "[3/5] 配置 Redis..."

REDIS_CONF="/etc/redis/redis.conf"
REDIS_CONF_BACKUP="${REDIS_CONF}.backup.$(date +%Y%m%d_%H%M%S)"

# 备份原始配置文件
if [ -f "$REDIS_CONF" ]; then
    cp "$REDIS_CONF" "$REDIS_CONF_BACKUP"
    echo "✓ 已备份配置文件: $REDIS_CONF_BACKUP"
fi

# 配置 Redis 监听地址（允许本地访问）
echo "配置 Redis 监听地址..."
sed -i 's/^bind 127.0.0.1 ::1/bind 127.0.0.1/' "$REDIS_CONF"
sed -i 's/^# bind 127.0.0.1/bind 127.0.0.1/' "$REDIS_CONF"

# 配置保护模式（仅本地访问时禁用）
echo "配置保护模式..."
sed -i 's/^protected-mode yes/protected-mode no/' "$REDIS_CONF"

# 配置持久化（可选，启用 RDB 快照）
echo "配置持久化..."
if ! grep -q "^save 900 1" "$REDIS_CONF"; then
    sed -i '/^# save /a save 900 1\nsave 300 10\nsave 60 10000' "$REDIS_CONF"
fi

# 配置日志级别
echo "配置日志级别..."
sed -i 's/^loglevel notice/loglevel notice/' "$REDIS_CONF"

# 配置最大内存（可选，根据系统内存调整）
echo "配置最大内存限制..."
if ! grep -q "^maxmemory" "$REDIS_CONF"; then
    # 设置最大内存为 256MB（可根据需要调整）
    echo "maxmemory 256mb" >> "$REDIS_CONF"
    echo "maxmemory-policy allkeys-lru" >> "$REDIS_CONF"
fi

echo "✓ Redis 配置完成"
echo ""

# ========================================
# 步骤 4: 启动 Redis 服务
# ========================================
echo "[4/5] 启动 Redis 服务..."

# 检查 Redis 服务状态
if systemctl is-active --quiet redis-server; then
    echo "✓ Redis 服务已在运行"
    systemctl restart redis-server
    echo "✓ Redis 服务已重启"
else
    systemctl start redis-server
    echo "✓ Redis 服务已启动"
fi

# 设置 Redis 服务开机自启
systemctl enable redis-server
echo "✓ Redis 服务已设置为开机自启"
echo ""

# ========================================
# 步骤 5: 测试 Redis 连接
# ========================================
echo "[5/5] 测试 Redis 连接..."

sleep 2  # 等待服务启动

if redis-cli ping | grep -q "PONG"; then
    echo "✓ Redis 连接测试成功"
else
    echo "❌ Redis 连接测试失败"
    echo "请检查 Redis 服务状态: sudo service redis-server status"
    exit 1
fi
echo ""

# ========================================
# 显示配置信息
# ========================================
echo "========================================"
echo "✓ Redis 安装和配置完成！"
echo "========================================"
echo ""
echo "Redis 配置信息："
echo "  - 监听地址: 127.0.0.1"
echo "  - 端口: 6379"
echo "  - 密码: （无密码，仅本地访问）"
echo "  - 配置文件: $REDIS_CONF"
echo ""
echo "常用命令："
echo "  启动服务: sudo service redis-server start"
echo "  停止服务: sudo service redis-server stop"
echo "  重启服务: sudo service redis-server restart"
echo "  查看状态: sudo service redis-server status"
echo "  测试连接: redis-cli ping"
echo "  进入 CLI: redis-cli"
echo ""
echo "从 Windows 访问："
echo "  使用 localhost:6379 或 127.0.0.1:6379"
echo ""

