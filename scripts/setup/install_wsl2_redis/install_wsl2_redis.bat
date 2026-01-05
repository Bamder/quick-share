@echo off
REM ========================================
REM QuickShare - WSL2 和 Redis 安装脚本
REM ========================================
REM ⭐ 这是用户入口脚本，请直接运行此脚本
REM ========================================
REM 此脚本将：
REM 1. 检查并安装 WSL2（如果未安装）
REM 2. 在 WSL2 中安装和配置 Redis
REM 3. 配置 Redis 以便 Windows 可以访问
REM ========================================
REM 注意：此脚本会自动调用 wsl_install_redis.sh
REM       用户无需手动运行 wsl_install_redis.sh
REM ========================================

setlocal enabledelayedexpansion

echo ========================================
echo QuickShare - WSL2 和 Redis 安装脚本
echo ========================================
echo.
echo ⭐ 这是用户入口脚本
echo    此脚本会自动调用 wsl_install_redis.sh（无需手动运行）
echo.

REM 检查管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误: 需要管理员权限
    echo.
    echo 请右键点击此脚本，选择"以管理员身份运行"
    echo.
    pause
    exit /b 1
)

echo ✓ 管理员权限检查通过
echo.

REM 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
set "WSL_SCRIPT=%SCRIPT_DIR%wsl_install_redis.sh"

REM ========================================
REM 步骤 1: 检查 WSL 是否已安装
REM ========================================
echo [1/4] 检查 WSL 安装状态...
wsl --status >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ WSL 已安装
    wsl --status
    echo.
) else (
    echo ⚠️  WSL 未安装，开始安装 WSL2...
    echo.
    echo 正在启用 WSL 功能...
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
    if !errorlevel! neq 0 (
        echo ❌ 启用 WSL 功能失败
        pause
        exit /b 1
    )
    
    echo 正在启用虚拟机平台功能...
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
    if !errorlevel! neq 0 (
        echo ❌ 启用虚拟机平台功能失败
        pause
        exit /b 1
    )
    
    echo.
    echo ⚠️  需要重启计算机以完成 WSL 安装
    echo.
    set /p RESTART="是否立即重启计算机？(Y/N): "
    if /i "!RESTART!"=="Y" (
        shutdown /r /t 0
        exit /b 0
    ) else (
        echo.
        echo 请手动重启计算机后，再次运行此脚本
        pause
        exit /b 0
    )
)

REM ========================================
REM 步骤 2: 检查 WSL 版本并设置为 WSL2
REM ========================================
echo.
echo [2/4] 检查 WSL 版本...
wsl --list --verbose >nul 2>&1
if %errorlevel% equ 0 (
    echo 当前 WSL 发行版列表：
    wsl --list --verbose
    echo.
    
    REM 使用 Python 脚本查找默认发行版（更可靠）
    set "DEFAULT_DISTRO="
    set "WSL_VERSION="
    
    REM 获取脚本所在目录
    set "SCRIPT_DIR=%~dp0"
    
    REM 调用 Python 脚本获取发行版信息
    for /f "tokens=1,2 delims=|" %%a in ('python "%SCRIPT_DIR%check_wsl_distro.py" 2^>nul') do (
        set "DEFAULT_DISTRO=%%a"
        set "WSL_VERSION=%%b"
    )
    
    if defined DEFAULT_DISTRO (
        echo 找到默认发行版: !DEFAULT_DISTRO!
        
        if "!WSL_VERSION!"=="2" (
            echo ✓ 默认发行版已使用 WSL2
        ) else if "!WSL_VERSION!"=="1" (
            echo ⚠️  默认发行版使用 WSL1，正在转换为 WSL2...
            wsl --set-version !DEFAULT_DISTRO! 2
            if !errorlevel! neq 0 (
                echo ❌ 转换为 WSL2 失败
                echo 请确保已安装 WSL2 内核更新
                echo 下载地址: https://aka.ms/wsl2kernel
                pause
                exit /b 1
            )
            echo ✓ 已转换为 WSL2
        ) else (
            echo ⚠️  无法确定 WSL 版本，假设已使用 WSL2
        )
    ) else (
        echo ⚠️  未找到已安装的 WSL 发行版
        echo 正在安装 Ubuntu（默认发行版）...
        wsl --install -d Ubuntu
        if !errorlevel! neq 0 (
            echo ❌ 安装 Ubuntu 失败
            echo 请手动安装 WSL 发行版后再次运行此脚本
            pause
            exit /b 1
        )
        echo.
        echo ⚠️  需要完成 Ubuntu 的初始设置
        echo 请按照提示设置用户名和密码，然后再次运行此脚本
        pause
        exit /b 0
    )
) else (
    echo ❌ 无法列出 WSL 发行版
    pause
    exit /b 1
)

REM ========================================
REM 步骤 3: 设置 WSL2 为默认版本
REM ========================================
echo.
echo [3/4] 设置 WSL2 为默认版本...
wsl --set-default-version 2 >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ WSL2 已设置为默认版本
) else (
    echo ⚠️  设置默认版本失败（可能已经是 WSL2）
)

REM ========================================
REM 步骤 4: 在 WSL2 中安装 Redis
REM ========================================
echo.
echo [4/4] 在 WSL2 中安装和配置 Redis...
echo.

REM 将安装脚本复制到 WSL 中
echo 正在准备 Redis 安装脚本...
if not exist "%WSL_SCRIPT%" (
    echo ❌ 找不到 Redis 安装脚本: %WSL_SCRIPT%
    pause
    exit /b 1
)

REM 将 Windows 路径转换为 WSL 路径
REM 使用 PowerShell 进行可靠的路径转换
echo 正在转换脚本路径...
for /f "delims=" %%p in ('powershell -Command "$p='%WSL_SCRIPT%'; $drive=$p.Substring(0,1).ToLower(); $path=$p.Substring(2).Replace('\','/'); '/mnt/' + $drive + $path"') do set "WSL_SCRIPT_PATH=%%p"

REM 在 WSL 中执行安装脚本
echo 正在在 WSL2 中执行 Redis 安装脚本...
echo [内部调用] wsl_install_redis.sh（由本脚本自动调用，无需手动运行）
echo.
wsl bash "%WSL_SCRIPT_PATH%"
if !errorlevel! neq 0 (
    echo.
    echo ❌ Redis 安装失败
    echo 请检查 WSL2 中的错误信息
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✓ WSL2 和 Redis 安装完成！
echo ========================================
echo.
echo Redis 配置信息：
echo   - 监听地址: 127.0.0.1
echo   - 端口: 6379
echo   - 密码: （无密码，仅本地访问）
echo.
echo 从 Windows 访问 Redis：
echo   使用 localhost:6379 或 127.0.0.1:6379
echo.
echo 测试连接：
echo   wsl redis-cli ping
echo.
echo 启动 Redis 服务：
echo   wsl sudo service redis-server start
echo.
echo 停止 Redis 服务：
echo   wsl sudo service redis-server stop
echo.
echo 查看 Redis 状态：
echo   wsl sudo service redis-server status
echo.
pause

