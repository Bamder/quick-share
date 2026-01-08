@echo off
REM 下载池测试运行脚本

echo ========================================
echo    下载池机制测试
echo ========================================
echo.

REM 使用Python 3.12测试环境运行测试
echo 正在使用Python 3.12测试环境运行下载池测试...
echo.

"%~dp0..\..\..\venv-test\Scripts\python.exe" "%~dp0test_download_pool.py"

echo.
echo 测试完成
pause
