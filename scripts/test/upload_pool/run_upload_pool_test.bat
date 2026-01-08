@echo off
REM 上传池测试运行脚本

echo ========================================
echo    上传池机制测试
echo ========================================
echo.

REM 使用Python 3.12测试环境运行测试
echo 正在使用Python 3.12测试环境运行上传池测试...
echo.

"%~dp0..\..\..\venv-test\Scripts\python.exe" "%~dp0test_upload_pool.py"

echo.
echo 测试完成
pause
