@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM 标识码映射机制测试运行脚本
REM 使用方法: 双击运行或在命令行中执行

REM 获取脚本所在目录并计算项目根目录
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\.."

REM 移除末尾的反斜杠
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

REM 切换到项目根目录（关键：确保能找到 .env 文件）
cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo [错误] 无法切换到项目根目录: %PROJECT_ROOT%
    pause
    exit /b 1
)

echo ========================================
echo    标识码映射机制测试
echo ========================================
echo.
echo [信息] 工作目录: %CD%
echo.

REM 使用Python 3.12测试环境运行测试
echo 正在使用Python 3.12测试环境运行标识码映射机制测试...
echo.

"%~dp0..\..\..\venv-test\Scripts\python.exe" "%~dp0test_mapping_mechanism.py"

echo.
echo 测试完成
pause
