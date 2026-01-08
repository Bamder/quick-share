@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 获取脚本所在目录并计算项目根目录
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\.."

:: 移除末尾的反斜杠
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

:: 切换到项目根目录
cd /d "%PROJECT_ROOT%"
if errorlevel 1 (
    echo [错误] 无法切换到项目根目录: %PROJECT_ROOT%
    pause
    exit /b 1
)

:: 检查是否在虚拟环境中
if not defined VIRTUAL_ENV (
    if exist "venv\Scripts\activate.bat" (
        call venv\Scripts\activate.bat >nul 2>&1
    )
)

:: 主菜单循环
:main_menu
cls
echo.
echo ========================================
echo    数据库结构强制同步工具（增强版）
echo ========================================
echo.
echo 请选择操作：
echo.
echo   1. 列出所有可用版本
echo   2. 显示当前版本信息
echo   3. 同步到最新版本（推荐）
echo   4. 同步到指定版本
echo   5. 比较版本差异
echo   6. 交互式选择版本并同步
echo   7. 生成同步报告
echo   8. 退出
echo.
set /p "choice=请输入选项 (1-8): "

if "%choice%"=="1" goto list_versions
if "%choice%"=="2" goto show_current
if "%choice%"=="3" goto sync_latest
if "%choice%"=="4" goto sync_target
if "%choice%"=="5" goto compare_versions
if "%choice%"=="6" goto interactive_sync
if "%choice%"=="7" goto generate_report
if "%choice%"=="8" goto exit_script
if "%choice%"=="" goto main_menu

echo [错误] 无效的选项，请重新选择
timeout /t 2 >nul
goto main_menu

:list_versions
cls
echo.
echo ========================================
echo    列出所有可用版本
echo ========================================
echo.
python "%SCRIPT_DIR%force_sync_database.py" --list --quiet
echo.
pause
goto main_menu

:show_current
cls
echo.
echo ========================================
echo    当前版本信息
echo ========================================
echo.
python "%SCRIPT_DIR%force_sync_database.py" --list --quiet
echo.
echo ========================================
echo.
set /p "back=按回车键返回主菜单..."
goto main_menu

:sync_latest
cls
echo.
echo ========================================
echo    同步到最新版本
echo ========================================
echo.
echo [信息] 正在同步数据库结构到最新版本...
echo.
python "%SCRIPT_DIR%force_sync_database.py" --quiet
set SYNC_RESULT=!errorlevel!
echo.
if !SYNC_RESULT! equ 0 (
    echo ========================================
    echo    [成功] 同步完成
    echo ========================================
) else (
    echo ========================================
    echo    [警告] 同步完成，但有部分问题
    echo ========================================
)
echo.
pause
goto main_menu

:sync_target
cls
echo.
echo ========================================
echo    同步到指定版本
echo ========================================
echo.
echo 正在加载可用版本列表...
echo.
python "%SCRIPT_DIR%force_sync_database.py" --list --quiet
echo.
echo ========================================
echo.
set /p "target_version=请输入目标版本号: "

if "!target_version!"=="" (
    echo [错误] 版本号不能为空
    timeout /t 2 >nul
    goto sync_target
)

echo.
echo [信息] 正在同步到版本: !target_version!
echo.
python "%SCRIPT_DIR%force_sync_database.py" --target "!target_version!" --quiet
set SYNC_RESULT=!errorlevel!
echo.
if !SYNC_RESULT! equ 0 (
    echo ========================================
    echo    [成功] 同步完成
    echo ========================================
) else (
    echo ========================================
    echo    [警告] 同步完成，但有部分问题
    echo ========================================
)
echo.
pause
goto main_menu

:compare_versions
cls
echo.
echo ========================================
echo    比较版本差异
echo ========================================
echo.
python "%SCRIPT_DIR%force_sync_database.py" --compare --quiet
echo.
echo ========================================
echo.
set /p "back=按回车键返回主菜单..."
goto main_menu

:interactive_sync
cls
echo.
echo ========================================
echo    交互式选择版本并同步
echo ========================================
echo.
python "%SCRIPT_DIR%force_sync_database.py" --interactive --quiet
set SYNC_RESULT=!errorlevel!
echo.
if !SYNC_RESULT! equ 0 (
    echo ========================================
    echo    [成功] 同步完成
    echo ========================================
) else (
    echo ========================================
    echo    [警告] 同步完成，但有部分问题
    echo ========================================
)
echo.
pause
goto main_menu

:generate_report
cls
echo.
echo ========================================
echo    生成同步报告
echo ========================================
echo.
set /p "report_file=请输入报告文件名（默认: sync_report.json）: "

if "!report_file!"=="" set "report_file=sync_report.json"

echo.
echo [信息] 正在同步并生成报告...
echo.
python "%SCRIPT_DIR%force_sync_database.py" --report "!report_file!" --quiet
set SYNC_RESULT=!errorlevel!
echo.
if !SYNC_RESULT! equ 0 (
    echo ========================================
    echo    [成功] 报告已生成
    echo ========================================
    echo    报告文件: !report_file!
) else (
    echo ========================================
    echo    [警告] 报告已生成，但同步有部分问题
    echo ========================================
    echo    报告文件: !report_file!
)
echo.
pause
goto main_menu

:exit_script
cls
echo.
echo 感谢使用！
echo.
timeout /t 1 >nul
exit /b 0

