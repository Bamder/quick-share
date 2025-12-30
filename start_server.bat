@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 获取脚本所在目录（项目根目录）
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: 设置项目根目录
set "PROJECT_ROOT=%CD%"

echo ========================================
echo    启动文件闪传系统 API 服务器
echo ========================================
echo.

:: 检查虚拟环境
set "VENV_PATH=%PROJECT_ROOT%\venv"
if not exist "!VENV_PATH!" (
    echo [警告] 未找到虚拟环境: !VENV_PATH!
    echo.
    echo 请先创建虚拟环境：
    echo   python -m venv venv
    echo.
    set /p CREATE_VENV="是否现在创建虚拟环境？(Y/N，默认: N): "
    if /i "!CREATE_VENV!"=="Y" (
        echo.
        echo 正在创建虚拟环境...
        python -m venv venv
        if errorlevel 1 (
            echo [错误] 创建虚拟环境失败
            pause
            exit /b 1
        )
        echo [成功] 虚拟环境已创建
        echo.
    ) else (
        echo [提示] 将使用系统 Python 环境
        echo.
        goto :check_dependencies
    )
)

:: 激活虚拟环境并设置 Python 路径
set "PYTHON_EXE=python"
if exist "!VENV_PATH!\Scripts\python.exe" (
    echo [信息] 正在激活虚拟环境...
    call "!VENV_PATH!\Scripts\activate.bat"
    if errorlevel 1 (
        echo [错误] 激活虚拟环境失败
        pause
        exit /b 1
    )
    :: 直接使用虚拟环境中的 Python
    set "PYTHON_EXE=!VENV_PATH!\Scripts\python.exe"
    echo [成功] 虚拟环境已激活
    echo [信息] 使用 Python: !PYTHON_EXE!
    echo.
) else (
    echo [警告] 虚拟环境 Python 不存在，使用系统 Python
    echo.
)

:check_dependencies
:: 检查关键依赖
echo [信息] 正在检查依赖...

:: 使用虚拟环境中的 Python 检查 uvicorn
"!PYTHON_EXE!" -c "import uvicorn" 2>nul
if errorlevel 1 (
    echo [警告] 未找到 uvicorn 模块
    echo.
    echo 请先安装依赖：
    echo   pip install -r requirements.txt
    echo.
    set /p INSTALL_DEPS="是否现在安装依赖？(Y/N，默认: N): "
    if /i "!INSTALL_DEPS!"=="Y" (
        echo.
        echo 正在安装依赖...
        if exist "!VENV_PATH!\Scripts\pip.exe" (
            "!VENV_PATH!\Scripts\pip.exe" install -r requirements.txt
        ) else (
            pip install -r requirements.txt
        )
        if errorlevel 1 (
            echo [错误] 安装依赖失败
            pause
            exit /b 1
        )
        echo [成功] 依赖已安装
        echo.
    ) else (
        echo [错误] 缺少必要依赖，无法启动服务器
        pause
        exit /b 1
    )
)

:: 检查 app 模块（显示详细错误信息）
echo [信息] 正在检查 app 模块...
"!PYTHON_EXE!" -c "import app.main" 2>error.tmp
if errorlevel 1 (
    echo [错误] 无法导入 app 模块
    echo.
    echo 详细错误信息：
    type error.tmp 2>nul
    del error.tmp 2>nul
    echo.
    echo 请检查：
    echo  1. 当前目录是否为项目根目录
    echo  2. app 目录是否存在
    echo  3. 依赖是否已正确安装（特别是 fastapi, pydantic-settings）
    echo  4. 虚拟环境是否已正确激活
    echo.
    echo 建议操作：
    echo  1. 确保虚拟环境已激活
    if exist "!VENV_PATH!\Scripts\pip.exe" (
        echo  2. 运行: !VENV_PATH!\Scripts\pip.exe install -r requirements.txt
    ) else (
        echo  2. 运行: pip install -r requirements.txt
    )
    echo  3. 重新运行此脚本
    echo.
    pause
    exit /b 1
)
del error.tmp 2>nul

echo [成功] 环境检查通过
echo.

:: 获取数据库配置信息
echo ========================================
echo    数据库配置
echo ========================================
echo.
echo 请输入数据库配置信息：
echo.

set /p DB_USER="数据库用户名 (默认: root): "
if "!DB_USER!"=="" set "DB_USER=root"

set /p DB_PASSWORD="数据库密码: "
if "!DB_PASSWORD!"=="" (
    echo [错误] 密码不能为空
    pause
    exit /b 1
)

set /p DB_HOST="数据库主机 (默认: localhost): "
if "!DB_HOST!"=="" set "DB_HOST=localhost"

set /p DB_PORT="数据库端口 (默认: 3306): "
if "!DB_PORT!"=="" set "DB_PORT=3306"

set /p DB_NAME="数据库名称 (默认: quick_share_datagrip): "
if "!DB_NAME!"=="" set "DB_NAME=quick_share_datagrip"

echo.
echo [信息] 数据库配置：
echo   主机: !DB_HOST!
echo   端口: !DB_PORT!
echo   用户: !DB_USER!
echo   数据库: !DB_NAME!
echo.
echo ========================================
echo    正在启动服务器...
echo ========================================
echo.

:: 切换到脚本目录并运行，传递数据库配置作为环境变量
cd /d "%PROJECT_ROOT%"
:: 将变量值设置到环境变量中（确保传递给子进程）
set "DB_HOST=!DB_HOST!"
set "DB_PORT=!DB_PORT!"
set "DB_USER=!DB_USER!"
set "DB_PASSWORD=!DB_PASSWORD!"
set "DB_NAME=!DB_NAME!"
"!PYTHON_EXE!" "scripts\run\start_server.py"

:: 如果脚本退出，暂停以便查看错误信息
if errorlevel 1 (
    echo.
    echo ========================================
    echo    服务器启动失败
    echo ========================================
    pause
)

endlocal

