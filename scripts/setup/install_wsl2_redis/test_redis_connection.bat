@echo off
REM ========================================
REM QuickShare - Redis 连接测试脚本
REM 辅助脚本
REM ========================================

echo ========================================
echo QuickShare - Redis 连接测试
echo ========================================
echo.

REM 检查 WSL 是否可用
wsl --status >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ WSL 未安装或未启动
    echo 请先运行 install_wsl2_redis.bat 安装 WSL2 和 Redis
    pause
    exit /b 1
)

echo [1/3] 检查 Redis 服务状态...
wsl sudo service redis-server status >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  Redis 服务未运行，正在启动...
    wsl sudo service redis-server start
    timeout /t 2 /nobreak >nul
)

echo.
echo [2/3] 测试 Redis 连接...
wsl redis-cli ping
if %errorlevel% equ 0 (
    echo ✓ Redis 连接测试成功
) else (
    echo ❌ Redis 连接测试失败
    echo.
    echo 请检查：
    echo   1. Redis 服务是否正在运行
    echo   2. 是否已正确安装 Redis
    pause
    exit /b 1
)

echo.
echo [3/3] 测试 Redis 基本操作...
wsl redis-cli set test_key "test_value" >nul 2>&1
wsl redis-cli get test_key | findstr "test_value" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Redis 读写测试成功
    wsl redis-cli del test_key >nul 2>&1
) else (
    echo ❌ Redis 读写测试失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✓ Redis 连接测试通过！
echo ========================================
echo.
echo Redis 配置信息：
echo   - 地址: localhost
echo   - 端口: 6379
echo   - 状态: 运行中
echo.
pause

