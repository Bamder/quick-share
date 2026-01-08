@echo off
chcp 65001 >nul
REM Python 测试环境设置脚本
REM 支持选择Python版本（默认为3.12）

echo ========================================
echo 设置Python测试环境
echo ========================================
echo.

REM 获取项目根目录
set "PROJECT_ROOT=%~dp0..\.."

echo 项目根目录: %PROJECT_ROOT%
echo.

REM 检查命令行参数（可选的Python版本）
set "DESIRED_PYTHON_VERSION=%~1"
if "%DESIRED_PYTHON_VERSION%"=="" (
    set "DESIRED_PYTHON_VERSION=3.12"
)

echo 期望的Python版本: %DESIRED_PYTHON_VERSION%
echo.

REM 检查Python是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python
    echo.
    echo 请确保Python已安装并在PATH中
    echo 或者使用完整路径运行此脚本:
    echo %0 [版本号]
    echo.
    pause
    exit /b 1
)

REM 检查Python版本是否匹配
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set CURRENT_PYTHON_VERSION=%%i
echo 当前Python版本: %CURRENT_PYTHON_VERSION%

echo %CURRENT_PYTHON_VERSION% | findstr "%DESIRED_PYTHON_VERSION%" >nul
if errorlevel 1 (
    echo ❌ Python版本不匹配 (期望: %DESIRED_PYTHON_VERSION%, 当前: %CURRENT_PYTHON_VERSION%)
    echo.
    echo 请按以下步骤设置正确的Python版本:
    echo.
    echo 方法1: 安装对应版本的Python
    echo 下载地址: https://www.python.org/downloads/
    echo 安装时勾选"Add Python to PATH"
    echo.
    echo 方法2: 使用pyenv管理多版本
    echo 安装pyenv-win: https://github.com/pyenv-win/pyenv-win
    echo pyenv install %DESIRED_PYTHON_VERSION%.0
    echo pyenv local %DESIRED_PYTHON_VERSION%.0
    echo.
    echo 方法3: 使用完整路径运行此脚本
    echo "C:\Python%DESIRED_PYTHON_VERSION%\python.exe" %0 %DESIRED_PYTHON_VERSION%
    echo.
    echo 或者继续使用当前版本? (按任意键继续，或Ctrl+C取消)
    pause >nul
) else (
    echo ✅ Python %DESIRED_PYTHON_VERSION% 版本检测通过
)
echo.

REM 检查测试环境是否存在
if exist "%PROJECT_ROOT%\venv-test\Scripts\python.exe" (
    echo ✅ 测试环境已存在
    echo.
    echo 如果要重新创建环境，请先删除 venv-test 目录
    echo 然后重新运行此脚本
    echo.
) else (
    echo 📦 创建Python %DESIRED_PYTHON_VERSION%测试环境...
    echo.

    REM 创建venv-test环境
    python -m venv "%PROJECT_ROOT%\venv-test"
    if errorlevel 1 (
        echo ❌ 创建测试环境失败
        pause
        exit /b 1
    )

    echo ✅ 测试环境创建成功
    echo.
)

REM 激活测试环境并安装依赖
echo 🔧 激活测试环境并安装依赖...
echo.

call "%PROJECT_ROOT%\venv-test\Scripts\activate.bat"
if errorlevel 1 (
    echo ❌ 激活测试环境失败
    pause
    exit /b 1
)

REM 升级pip
python -m pip install --upgrade pip

REM 安装项目依赖
echo 正在安装项目依赖...
pip install -r "%PROJECT_ROOT%\requirements.txt"
if errorlevel 1 (
    echo ❌ 安装项目依赖失败
    pause
    exit /b 1
)

REM 安装测试专用依赖
echo 正在安装测试依赖...
pip install -r "%PROJECT_ROOT%\scripts\test\test-requirements.txt"
if errorlevel 1 (
    echo ❌ 安装测试依赖失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ Python %DESIRED_PYTHON_VERSION%测试环境设置完成！
echo ========================================
echo.
echo 测试环境位置: %PROJECT_ROOT%\venv-test
echo Python版本: %DESIRED_PYTHON_VERSION% (当前环境版本)
echo.
echo 使用方法:
echo 1. 运行单个测试: scripts\test\auth\run_auth_test.bat
echo 2. 或直接运行: venv-test\Scripts\python.exe scripts\test\auth\test_auth.py
echo.
echo 注意:
echo - 项目主环境 (venv) 继续使用Python 3.13.5
echo - 测试环境 (venv-test) 使用Python %DESIRED_PYTHON_VERSION%以获得更好的兼容性
echo - 如需使用其他Python版本，请运行: %0 [版本号]
echo.
pause
