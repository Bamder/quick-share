@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: 设置项目根目录
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\.."
cd /d "%PROJECT_ROOT%"

echo ========================================
echo   生成自签名SSL证书
echo ========================================
echo.

:: 检查虚拟环境
set "VENV_PATH=%PROJECT_ROOT%\venv"
set "PYTHON_EXE=python"

if exist "!VENV_PATH!\Scripts\python.exe" (
    set "PYTHON_EXE=!VENV_PATH!\Scripts\python.exe"
    echo [信息] 使用虚拟环境中的 Python
    echo.
) else (
    echo [信息] 使用系统 Python
    echo.
)

:: 检查 cryptography 库
echo [信息] 检查依赖库...
"!PYTHON_EXE!" -c "import cryptography" >nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 cryptography 库，正在安装...
    "!PYTHON_EXE!" -m pip install cryptography --quiet
    if errorlevel 1 (
        echo [错误] 安装 cryptography 库失败
        echo 请手动运行: pip install cryptography
        pause
        exit /b 1
    )
)

:: 运行证书生成脚本
"!PYTHON_EXE!" "scripts\setup\generate_ssl_cert\generate_ssl_cert.py"

pause

