@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 获取脚本所在目录并计算项目根目录
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%..\..\.."

:: 移除末尾的反斜杠，确保路径正确
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

echo 脚本目录: %SCRIPT_DIR%
echo 项目根目录: %PROJECT_ROOT%
echo.

:: 检查项目根目录是否存在
if not exist "%PROJECT_ROOT%" (
    echo [错误] 项目根目录不存在: %PROJECT_ROOT%
    pause
    exit /b 1
)
cd /d "%PROJECT_ROOT%"

echo ========================================
echo    安装项目依赖
echo ========================================
echo.

:: 检查 Python 是否安装
echo 正在检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python
    echo.
    echo 请访问 https://www.python.org/downloads/ 下载并安装 Python
    pause
    exit /b 1
)
python --version
echo [成功] Python 环境正常
echo.

:: 检查 pip 是否安装
echo 正在检查 pip...
pip --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 pip，请先安装 pip
    echo.
    echo 请运行以下命令安装 pip：
    echo python -m ensurepip --upgrade
    pause
    exit /b 1
)
pip --version
echo [成功] pip 环境正常
echo.

:: 检查 requirements.txt 是否存在
if not exist "requirements.txt" (
    echo [错误] 未找到 requirements.txt 文件
    echo 请确保 requirements.txt 文件存在于项目根目录
    pause
    exit /b 1
)

:: 询问是否使用虚拟环境
echo ========================================
echo    安装选项
echo ========================================
echo.
echo [提示] 建议在虚拟环境中安装依赖
echo.
set /p USE_VENV="是否创建并使用虚拟环境？(Y/N，默认: Y): "
if /i "!USE_VENV!"=="" set "USE_VENV=Y"

if /i "!USE_VENV!"=="Y" (
    echo.
    echo 正在检查虚拟环境...
    
    :: 检查是否已存在虚拟环境
    if exist "venv\Scripts\activate.bat" (
        echo [提示] 检测到已存在的虚拟环境
        set /p REUSE_VENV="是否使用现有虚拟环境？(Y/N，默认: Y): "
        if /i "!REUSE_VENV!"=="" set "REUSE_VENV=Y"
        
        if /i "!REUSE_VENV!"=="Y" (
            echo 正在激活虚拟环境...
            call venv\Scripts\activate.bat
            if errorlevel 1 (
                echo [警告] 虚拟环境激活失败，将在全局环境安装
                set "USE_VENV=N"
            ) else (
                echo [成功] 虚拟环境已激活
            )
        ) else (
            echo 正在创建新的虚拟环境...
            python -m venv venv
            if errorlevel 1 (
                echo [错误] 虚拟环境创建失败
                pause
                exit /b 1
            )
            echo [成功] 虚拟环境创建成功
            echo 正在激活虚拟环境...
            call venv\Scripts\activate.bat
            if errorlevel 1 (
                echo [错误] 虚拟环境激活失败
                pause
                exit /b 1
            )
            echo [成功] 虚拟环境已激活
        )
    ) else (
        echo 正在创建虚拟环境...
        python -m venv venv
        if errorlevel 1 (
            echo [错误] 虚拟环境创建失败
            pause
            exit /b 1
        )
        echo [成功] 虚拟环境创建成功
        echo 正在激活虚拟环境...
        call venv\Scripts\activate.bat
        if errorlevel 1 (
            echo [错误] 虚拟环境激活失败
            pause
            exit /b 1
        )
        echo [成功] 虚拟环境已激活
    )
    echo.
)

:: 升级 pip
echo ========================================
echo    升级 pip
echo ========================================
echo.
echo 正在升级 pip 到最新版本...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [警告] pip 升级失败，继续安装依赖...
) else (
    echo [成功] pip 已升级到最新版本
)
echo.

:: 安装依赖
echo ========================================
echo    安装项目依赖
echo ========================================
echo.
echo 正在从 requirements.txt 安装依赖...
echo.

pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败
    echo.
    echo 可能的原因：
    echo 1. 网络连接问题
    echo 2. requirements.txt 中的包名或版本不正确
    echo 3. 缺少编译工具（某些包需要编译）
    echo.
    echo 建议：
    echo 1. 检查网络连接
    echo 2. 尝试单独安装失败的包
    echo 3. 查看上方的错误信息
    echo.
    pause
    exit /b 1
)

echo.
echo [成功] 所有依赖安装完成
echo.

:: 显示已安装的包
echo ========================================
echo    已安装的包
echo ========================================
echo.
pip list
echo.

:: 提示信息
if /i "!USE_VENV!"=="Y" (
    echo ========================================
    echo    重要提示
    echo ========================================
    echo.
    echo [提示] 您正在使用虚拟环境
    echo 每次使用项目时，请先激活虚拟环境：
    echo   venv\Scripts\activate.bat
    echo.
    echo 退出虚拟环境：
    echo   deactivate
    echo.
)

echo ========================================
echo    安装完成！
echo ========================================
echo.
pause

