@echo off
chcp 65001 >nul
REM 运行文件缓存与上传用户强绑定测试

echo ========================================
echo 文件缓存与上传用户强绑定测试
echo ========================================
echo.

REM 获取脚本所在目录并计算项目根目录
REM 脚本位置: scripts/test/file_cache_user_binding/run_test.bat
REM 需要向上3层到达项目根目录
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\.."

REM 移除末尾的反斜杠，确保路径正确
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

echo 脚本目录: %SCRIPT_DIR%
echo 项目根目录: %PROJECT_ROOT%
echo.

REM 检查项目根目录是否存在
if not exist "%PROJECT_ROOT%" (
    echo 错误: 项目根目录不存在: %PROJECT_ROOT%
    pause
    exit /b 1
)

REM 切换到项目根目录
cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo 错误: 无法切换到项目根目录: %PROJECT_ROOT%
    pause
    exit /b 1
)

echo 当前工作目录: %CD%
echo.

REM 检查 Python 脚本是否存在
if not exist "scripts\test\file_cache_user_binding\test_file_cache_user_binding.py" (
    echo 错误: Python 脚本不存在: scripts\test\file_cache_user_binding\test_file_cache_user_binding.py
    pause
    exit /b 1
)

REM 选择 Python 可执行文件（优先使用虚拟环境的 python.exe，无需 activate）
set "PY_EXE="
if exist "venv\Scripts\python.exe" (
    set "PY_EXE=venv\Scripts\python.exe"
    echo ✓ 找到虚拟环境 Python: !PY_EXE!
) else if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
    echo ✓ 找到虚拟环境 Python: !PY_EXE!
) else (
    set "PY_EXE=python"
    echo ⚠️ 未找到虚拟环境，使用系统 Python: !PY_EXE!
    echo 如需虚拟环境，请先创建: python -m venv venv
    echo.
)

REM 检查 Python 是否可用
"%PY_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo 错误: Python 不可用: %PY_EXE%
    pause
    exit /b 1
)

echo.
echo 运行测试脚本...
echo 命令: "%PY_EXE%" "scripts\test\file_cache_user_binding\test_file_cache_user_binding.py"
echo.

REM 运行测试脚本
"%PY_EXE%" "scripts\test\file_cache_user_binding\test_file_cache_user_binding.py"
set SCRIPT_EXIT_CODE=%errorlevel%

echo.
echo ========================================
if %SCRIPT_EXIT_CODE% equ 0 (
    echo ✓ 测试执行成功完成
) else (
    echo ✗ 测试执行失败 (退出码: %SCRIPT_EXIT_CODE%)
)
echo ========================================
pause

