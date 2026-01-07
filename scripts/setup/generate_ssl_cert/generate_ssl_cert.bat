@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 获取脚本所在目录并计算项目根目录
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\.."

:: 移除末尾的反斜杠，确保路径正确
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

echo 脚本目录: %SCRIPT_DIR%
echo 项目根目录: %PROJECT_ROOT%
echo.

:: 检查项目根目录是否存在
if not exist "%PROJECT_ROOT%" (
    echo [错误] 项目根目录不存在: %PROJECT_ROOT%
    pause
    exit /b 1
)

:: 切换到项目根目录
cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo [错误] 无法切换到项目根目录: %PROJECT_ROOT%
    pause
    exit /b 1
)

echo 当前工作目录: %CD%
echo.

:: 检查 Python 脚本是否存在
if not exist "scripts\setup\generate_ssl_cert\generate_ssl_cert.py" (
    echo [错误] Python 脚本不存在: scripts\setup\generate_ssl_cert\generate_ssl_cert.py
    pause
    exit /b 1
)

echo ========================================
echo   生成自签名SSL证书
echo ========================================
echo.

:: 选择 Python 可执行文件（优先使用虚拟环境的 python.exe，无需 activate）
set "PYTHON_EXE="
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
    echo ✓ 找到虚拟环境 Python: !PYTHON_EXE!
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo ✓ 找到虚拟环境 Python: !PYTHON_EXE!
) else (
    set "PYTHON_EXE=python"
    echo ⚠️ 未找到虚拟环境，使用系统 Python: !PYTHON_EXE!
    echo 如需虚拟环境，请先创建: python -m venv venv
    echo.
)

:: 检查 Python 是否可用
"!PYTHON_EXE!" --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 不可用: %PYTHON_EXE%
    pause
    exit /b 1
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
echo.
echo 运行证书生成脚本...
echo 命令: "!PYTHON_EXE!" "scripts\setup\generate_ssl_cert\generate_ssl_cert.py"
echo.

"!PYTHON_EXE!" "scripts\setup\generate_ssl_cert\generate_ssl_cert.py"
set SCRIPT_EXIT_CODE=%errorlevel%

echo.
echo ========================================
if %SCRIPT_EXIT_CODE% equ 0 (
    echo ✓ 脚本执行成功完成
) else (
    echo ✗ 脚本执行失败 (退出码: %SCRIPT_EXIT_CODE%)
)
echo ========================================
pause

