@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 获取脚本所在目录和项目根目录
set "SCRIPT_DIR=%~dp0"
:: 将相对路径转换为绝对路径
cd /d "%SCRIPT_DIR%..\..\..\"
set "PROJECT_ROOT=%CD%"
cd /d "%PROJECT_ROOT%"

echo ========================================
echo    数据库迁移脚本
echo ========================================
echo.

:: 检查 Python 是否安装
echo 正在检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python
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
    pause
    exit /b 1
)
pip --version
echo [成功] pip 环境正常
echo.

:: 检查并激活虚拟环境
echo ========================================
echo    检查虚拟环境
echo ========================================
echo.

:: 检查是否已经在虚拟环境中（通过检查 VIRTUAL_ENV 环境变量）
if defined VIRTUAL_ENV (
    echo [提示] 已在虚拟环境中: !VIRTUAL_ENV!
    echo.
) else (
    :: 不在虚拟环境中，检查是否存在虚拟环境目录
    if exist "venv\Scripts\activate.bat" (
        echo [提示] 检测到虚拟环境，正在激活...
        call venv\Scripts\activate.bat
        if errorlevel 1 (
            echo [警告] 虚拟环境激活失败
            echo [提示] 请手动激活虚拟环境后再运行此脚本
            echo 激活命令: venv\Scripts\activate.bat
            echo.
            set /p CONTINUE="是否继续在全局环境运行？(Y/N，默认: N): "
            if /i not "!CONTINUE!"=="Y" (
                echo [提示] 已取消，请先激活虚拟环境
                pause
                exit /b 1
            )
        ) else (
            echo [成功] 虚拟环境已激活
            echo.
        )
    ) else (
        echo [警告] 未检测到虚拟环境
        echo.
        echo [提示] 建议先运行依赖安装脚本创建虚拟环境：
        echo   scripts\setup\install_dependencies\install_dependencies.bat
        echo.
        set /p CONTINUE="是否继续在全局环境运行？(Y/N，默认: N): "
        if /i not "!CONTINUE!"=="Y" (
            echo [提示] 已取消，请先安装依赖并创建虚拟环境
            pause
            exit /b 1
        )
        echo [提示] 将在全局环境运行，建议使用虚拟环境
        echo.
    )
)

:: 第一步：安装依赖库（提前检测，确保 Python 脚本可以正常运行）
echo ========================================
echo    第一步：安装依赖库
echo ========================================
echo.
echo 正在安装依赖库...
if exist "requirements.txt" (
    echo 正在从 requirements.txt 安装依赖...
    pip install -r requirements.txt
) else (
    echo [警告] 未找到 requirements.txt，安装基础依赖...
    pip install alembic sqlalchemy pymysql cryptography
)
if errorlevel 1 (
    echo [错误] 依赖库安装失败
    echo [提示] 请检查网络连接或手动运行: pip install -r requirements.txt
    pause
    exit /b 1
)
echo [成功] 依赖库安装完成
echo.

:: 第二步：检查 MySQL 服务状态（使用 Python 脚本，避免批处理转义问题）
echo ========================================
echo    第二步：检查 MySQL 服务状态
echo ========================================
echo.

:: 使用 Python 脚本检测和启动 MySQL 服务
set "MYSQL_SERVICE="
set "MYSQL_SERVICE_RUNNING=0"
set "TEMP_FILE=!TEMP!\mysql_svc_!RANDOM!.tmp"

cd /d "!SCRIPT_DIR!"
python check_mysql_service.py > "!TEMP_FILE!" 2>nul
cd /d "!PROJECT_ROOT!"

if exist "!TEMP_FILE!" (
    for /f "usebackq delims=" %%a in ("!TEMP_FILE!") do (
        set "SERVICE_OUTPUT=%%a"
    )
    del "!TEMP_FILE!" >nul 2>&1
)

:: 解析输出：格式为 STATUS|SERVICE_NAME 或 STATUS|SERVICE_NAME|EXTRA_INFO
if defined SERVICE_OUTPUT (
    for /f "tokens=1,2,3 delims=|" %%a in ("!SERVICE_OUTPUT!") do (
        set "SERVICE_STATUS=%%a"
        set "MYSQL_SERVICE=%%b"
        set "EXTRA_INFO=%%c"
    )
)

if defined MYSQL_SERVICE (
    if "!SERVICE_STATUS!"=="RUNNING" (
        echo [成功] MySQL 服务正在运行: !MYSQL_SERVICE!
        set "MYSQL_SERVICE_RUNNING=1"
    ) else if "!SERVICE_STATUS!"=="STOPPED" (
        echo [警告] MySQL 服务未运行: !MYSQL_SERVICE!
        echo.
        set /p CONTINUE="是否尝试自动启动服务？(需要管理员权限，Y/N，默认: N): "
        if /i "!CONTINUE!"=="Y" (
            echo 正在尝试启动 MySQL 服务...
            cd /d "!SCRIPT_DIR!"
            python check_mysql_service.py --auto-start > "!TEMP_FILE!" 2>nul
            cd /d "!PROJECT_ROOT!"
            if exist "!TEMP_FILE!" (
                for /f "usebackq delims=" %%a in ("!TEMP_FILE!") do (
                    set "SERVICE_OUTPUT=%%a"
                )
                del "!TEMP_FILE!" >nul 2>&1
                for /f "tokens=1,2,3 delims=|" %%a in ("!SERVICE_OUTPUT!") do (
                    if "%%a"=="RUNNING" (
                        echo [成功] MySQL 服务已启动: %%b
                        set "MYSQL_SERVICE_RUNNING=1"
                    ) else (
                        echo [错误] 自动启动失败，可能需要管理员权限
                        echo.
                        echo [提示] 请手动启动 MySQL 服务：
                        echo 1. 按 Win+R，输入 services.msc，回车
                        echo 2. 找到 MySQL 服务并启动
                        echo 或者以管理员身份运行: net start "!MYSQL_SERVICE!"
                        echo.
                        set /p MANUAL_START="是否已完成手动启动？(Y/N，默认: N): "
                        if /i "!MANUAL_START!"=="Y" (
                            echo 正在重新检测服务状态...
                            cd /d "!SCRIPT_DIR!"
                            python check_mysql_service.py > "!TEMP_FILE!" 2>nul
                            cd /d "!PROJECT_ROOT!"
                            if exist "!TEMP_FILE!" (
                                for /f "usebackq delims=" %%x in ("!TEMP_FILE!") do (
                                    set "SERVICE_OUTPUT=%%x"
                                )
                                del "!TEMP_FILE!" >nul 2>&1
                                for /f "tokens=1,2 delims=|" %%x in ("!SERVICE_OUTPUT!") do (
                                    if "%%x"=="RUNNING" (
                                        echo [成功] 检测到 MySQL 服务正在运行: %%y
                                        set "MYSQL_SERVICE_RUNNING=1"
                                    ) else (
                                        echo [警告] 服务仍未运行，请确认服务已启动
                                        set /p CONTINUE3="是否继续尝试连接？(Y/N，默认: N): "
                                        if /i not "!CONTINUE3!"=="Y" (
                                            echo [提示] 已取消，请先启动 MySQL 服务
                                            pause
                                            exit /b 1
                                        )
                                    )
                                )
                            )
                        ) else (
                            set /p CONTINUE2="是否继续尝试连接？(Y/N，默认: N): "
                            if /i not "!CONTINUE2!"=="Y" (
                                echo [提示] 已取消，请先启动 MySQL 服务
                                pause
                                exit /b 1
                            )
                        )
                    )
                )
            )
        ) else (
            set /p CONTINUE2="是否继续尝试连接？(Y/N，默认: N): "
            if /i not "!CONTINUE2!"=="Y" (
                echo [提示] 已取消，请先启动 MySQL 服务
                pause
                exit /b 1
            )
        )
    )
) else (
    echo [警告] 未检测到 MySQL 服务
    echo.
    echo [提示] 请检查 MySQL 是否已安装，或手动启动 MySQL 服务
    echo.
    set /p CONTINUE="是否继续尝试连接？(Y/N，默认: N): "
    if /i not "!CONTINUE!"=="Y" (
        echo [提示] 已取消，请先安装或启动 MySQL 服务
        pause
        exit /b 1
    )
)
echo.

:: 第三步：创建数据库（使用 Python 脚本自动创建）
echo ========================================
echo    第二步：创建数据库
echo ========================================
echo.

:: 提示用户输入数据库配置信息（这些信息后续也会用到）
echo 请输入数据库配置信息：
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

set "DB_NAME=quick_share_datagrip"

echo.
echo 正在使用 Python 脚本创建数据库...
python "%SCRIPT_DIR%\create_database.py" "!DB_HOST!" "!DB_PORT!" "!DB_USER!" "!DB_PASSWORD!" "!DB_NAME!"
if errorlevel 1 (
    echo.
    echo [错误] 数据库创建失败
    echo.
    echo 可能的原因：
    echo 1. MySQL 服务未运行（请检查服务状态）
    echo 2. 用户名或密码错误
    echo 3. 用户没有创建数据库的权限
    echo 4. 端口号不正确
    echo.
    echo 解决方法：
    echo 1. 确认 MySQL 服务已启动
    echo 2. 检查用户名和密码是否正确
    echo 3. 尝试使用 MySQL 命令行工具连接测试：
    echo    mysql -u !DB_USER! -p -h !DB_HOST! -P !DB_PORT!
    echo.
    pause
    exit /b 1
)
echo.

:: 第四步：配置 Alembic
echo ========================================
echo    第四步：配置 Alembic
echo ========================================
echo.

:: 检查 alembic.ini.example 是否存在（在脚本目录中）
set "ALEMBIC_INI_EXAMPLE=%SCRIPT_DIR%\alembic.ini.example"
if not exist "!ALEMBIC_INI_EXAMPLE!" (
    echo [错误] 未找到 alembic.ini.example 文件: !ALEMBIC_INI_EXAMPLE!
    pause
    exit /b 1
)

:: 如果项目根目录的 alembic.ini 不存在，则从脚本目录复制并配置
set "ALEMBIC_INI=%PROJECT_ROOT%\alembic.ini"
if not exist "!ALEMBIC_INI!" (
    echo 正在从脚本目录复制 alembic.ini.example 到项目根目录...
    copy /Y "!ALEMBIC_INI_EXAMPLE!" "!ALEMBIC_INI!" >nul
    if errorlevel 1 (
        echo [错误] 复制配置文件失败
        pause
        exit /b 1
    )
    echo [成功] 配置文件已创建: !ALEMBIC_INI!
    echo.
) else (
    echo [提示] alembic.ini 已存在，将使用新的配置信息更新
    echo.
)

echo 正在配置 alembic.ini...

:: 使用 Python 脚本配置 alembic.ini（更简单、更可靠）
:: 确保使用绝对路径调用 Python 脚本
set "CONFIG_SCRIPT=%SCRIPT_DIR%\configure_alembic.py"
if not exist "!CONFIG_SCRIPT!" (
    echo [错误] 未找到配置脚本: !CONFIG_SCRIPT!
    pause
    exit /b 1
)

:: 使用 call 确保参数正确传递，并切换到脚本目录执行
cd /d "!SCRIPT_DIR!"
python "configure_alembic.py" "!PROJECT_ROOT!" "!DB_USER!" "!DB_PASSWORD!" "!DB_HOST!" "!DB_PORT!" "!DB_NAME!"
set CONFIG_RESULT=!errorlevel!
cd /d "!PROJECT_ROOT!"

if !CONFIG_RESULT! neq 0 (
    echo.
    echo ========================================
    echo    [错误] 自动配置失败
    echo ========================================
    echo.
    echo 请按照以下步骤手动配置：
    echo.
    echo 1. 打开项目根目录下的 alembic.ini 文件
    echo 2. 找到第87行左右的 sqlalchemy.url 配置项
    echo 3. 将其替换为以下内容：
    echo.
    echo    sqlalchemy.url = mysql+pymysql://!DB_USER!:!DB_PASSWORD!@!DB_HOST!:!DB_PORT!/!DB_NAME!?charset=utf8mb4
    echo.
    echo 4. 保存文件
    echo 5. 重新运行此脚本
    echo.
    echo 详细说明已保存到: %SCRIPT_DIR%\manual_config_guide.txt
    echo.
    echo ========================================
    set /p CONTINUE_CONFIG="是否已手动配置完成？(Y/N，默认: N): "
    if /i not "!CONTINUE_CONFIG!"=="Y" (
        echo.
        echo [提示] 已取消，请先配置 alembic.ini 后再运行此脚本
        echo.
        pause
        exit /b 1
    )
    echo.
    echo [提示] 将继续执行迁移步骤...
    echo.
) else (
    echo [成功] 配置文件已更新
)
echo.

:: 第五步：执行数据库迁移
echo ========================================
echo    第五步：执行数据库迁移
echo ========================================
echo.
echo [信息] 正在检查并执行数据库迁移（alembic upgrade head）...
echo [提示] 这将应用所有待执行的迁移脚本，更新数据库结构
echo.

:: 检查 alembic 是否可用
where alembic >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 alembic 命令
    echo [提示] 请确保虚拟环境已激活，并且已安装依赖库
    echo [提示] 如果使用虚拟环境，请运行: venv\Scripts\activate.bat
    echo [提示] 然后运行: pip install -r requirements.txt
    pause
    exit /b 1
)

:: 执行迁移
alembic upgrade head
if errorlevel 1 (
    echo.
    echo ========================================
    echo    [错误] 数据库迁移失败
    echo ========================================
    echo.
    echo 可能的原因：
    echo 1. MySQL 服务未运行
    echo 2. 有未安装的依赖软件库（如 pymysql）
    echo 3. alembic.ini 中的 url 配置错误（用户名、密码、主机、端口）
    echo 4. 数据库连接失败（Access denied 表示用户名或密码错误）
    echo 5. 数据库不存在
    echo.
    echo 常见错误解决：
    echo - "Access denied"：用户名或密码错误，请检查 alembic.ini 中的配置
    echo - "Can't connect"：MySQL 服务未运行，请启动服务
    echo - "Unknown database"：数据库不存在，请先创建数据库
    echo - "ModuleNotFoundError: No module named 'pymysql'"：未安装依赖，请运行 pip install -r requirements.txt
    echo.
    echo 当前 alembic.ini 配置：
    findstr /C:"sqlalchemy.url" alembic.ini 2>nul
    echo.
    echo 建议将完整的报错信息复制到 AI 工具中分析解决
    echo.
    pause
    exit /b 1
)
echo.
echo [成功] 数据库迁移成功
echo.

:: 第六步：提示验证
echo ========================================
echo    第六步：验证迁移结果
echo ========================================
echo.
echo [提示] 请在 MySQL 命令行中执行以下命令验证迁移结果：
echo.
echo USE quick_share_datagrip;
echo SHOW TABLES;
echo.
echo 如果显示数据库表列表，则表示迁移成功。
echo.

echo ========================================
echo    迁移流程完成！
echo ========================================
echo.
pause

