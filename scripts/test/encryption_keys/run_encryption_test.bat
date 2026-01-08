@echo off
REM 加密密钥测试运行脚本

echo ========================================
echo    加密密钥机制测试
echo ========================================
echo.

REM 使用Python 3.12测试环境运行测试
echo 正在使用Python 3.12测试环境运行加密密钥测试...
echo.

"%~dp0..\..\..\venv-test\Scripts\python.exe" "%~dp0test_encryption_keys.py"

echo.
echo 测试完成
pause
