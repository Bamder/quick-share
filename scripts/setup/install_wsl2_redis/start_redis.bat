@echo off
REM ========================================
REM QuickShare - 启动 Redis 服务
REM 辅助脚本
REM ========================================

echo ========================================
echo QuickShare - 启动 Redis 服务
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

echo 正在启动 Redis 服务...
wsl sudo service redis-server start

if %errorlevel% equ 0 (
    echo.
    echo ✓ Redis 服务已启动
    echo.
    echo 测试连接...
    timeout /t 1 /nobreak >nul
    wsl redis-cli ping
    if %errorlevel% equ 0 (
        echo.
        echo ✓ Redis 运行正常
    )
) else (
    echo.
    echo ❌ Redis 服务启动失败
    echo 请检查 Redis 是否已正确安装
)

echo.
pause

