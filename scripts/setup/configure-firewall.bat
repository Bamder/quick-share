@echo off
REM Windows 防火墙配置脚本
REM 为 QuickShare 文件闪传系统添加防火墙规则，允许端口 8000 的入站连接

echo ========================================
echo QuickShare 文件闪传系统 - Windows 防火墙配置
echo ========================================
echo.
echo 此脚本将为 QuickShare 文件闪传系统添加防火墙规则
echo 允许端口 8000 的 TCP 入站连接
echo.

REM 检查管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误: 需要管理员权限
    echo.
    echo 请右键点击此脚本，选择"以管理员身份运行"
    echo.
    pause
    exit /b 1
)

echo ✅ 已检测到管理员权限
echo.
echo 正在配置防火墙规则...
echo.

REM 删除可能存在的旧规则（如果存在）
netsh advfirewall firewall delete rule name="QuickShare Server" >nul 2>&1

REM 添加新的防火墙规则
netsh advfirewall firewall add rule name="QuickShare Server" dir=in action=allow protocol=TCP localport=8000

if %errorlevel% equ 0 (
    echo ✅ 防火墙规则添加成功！
    echo.
    echo 现在其他设备可以通过以下地址访问文件闪传系统：
    echo   - HTTP: http://[服务器IP]:8000
    echo   - API 文档: http://[服务器IP]:8000/docs
    echo   - 健康检查: http://[服务器IP]:8000/health
    echo.
    echo 提示：运行 start_server.bat 查看服务器的 IP 地址
    echo.
) else (
    echo ❌ 防火墙规则添加失败
    echo.
    echo 错误代码: %errorlevel%
    echo 请尝试手动配置防火墙：
    echo   1. 打开"Windows 安全中心" ^> "防火墙和网络保护"
    echo   2. 点击"高级设置" ^> "入站规则" ^> "新建规则"
    echo   3. 选择"端口" ^> "TCP" ^> 特定本地端口: 8000
    echo   4. 选择"允许连接" ^> 完成
    echo.
)

pause

