@echo off
REM 取件码测试运行脚本
REM 使用方法: 双击运行或在命令行中执行

echo ========================================
echo    12位取件码系统测试
echo ========================================
echo.

REM 使用Python 3.12测试环境运行测试
echo 正在使用Python 3.12测试环境运行取件码测试...
echo.

"%~dp0..\..\..\venv-test\Scripts\python.exe" "%~dp0test_pickup_code.py"

echo.
echo 测试完成
pause
