@echo off
REM 用户认证测试运行脚本
REM 使用方法: 双击运行或在命令行中执行

echo ========================================
echo    用户认证系统测试
echo ========================================
echo.

REM 使用Python 3.12测试环境运行测试
echo 正在使用Python 3.12测试环境运行用户认证测试...
echo.

"%~dp0..\..\..\venv-test\Scripts\python.exe" "%~dp0test_auth.py"

echo.
echo 测试完成
pause
