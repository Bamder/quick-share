@echo off
REM ========================================
REM QuickShare - 停止 Redis 服务
REM 辅助脚本
REM ========================================

echo ========================================
echo QuickShare - 停止 Redis 服务
echo ========================================
echo.

REM 检查 WSL 是否可用
wsl --status >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ WSL 未安装或未启动
    pause
    exit /b 1
)

echo 正在停止 Redis 服务...
wsl sudo service redis-server stop

if %errorlevel% equ 0 (
    echo.
    echo ✓ Redis 服务已停止
) else (
    echo.
    echo ⚠️  Redis 服务可能未运行或已停止
)

echo.
pause

