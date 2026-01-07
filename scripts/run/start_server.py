"""
启动文件闪传系统 API 服务器
"""
import sys
import os
import socket

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 添加 scripts 目录到 Python 路径（用于导入 scripts/utils 中的工具）
scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

# 从配置文件读取配置（支持 .env 文件）
# 使用 app.config.Settings 自动加载 .env 文件中的配置
try:
    from app.config import settings
except ImportError:
    print("=" * 50)
    print("❌ 错误：无法导入配置模块")
    print("=" * 50)
    print("请确认 app/config.py 文件存在")
    sys.exit(1)

# 从配置对象读取数据库配置
db_host = settings.DB_HOST
db_port = settings.DB_PORT
db_user = settings.DB_USER
db_password = settings.DB_PASSWORD
db_name = settings.DB_NAME

# 从配置对象读取 Redis 配置
redis_enabled = settings.REDIS_ENABLED
redis_host = settings.REDIS_HOST
redis_port = settings.REDIS_PORT
redis_password = settings.REDIS_PASSWORD
redis_db = settings.REDIS_DB

# 设置环境变量，供其他模块读取（保持兼容性）
os.environ["DB_HOST"] = str(db_host)
os.environ["DB_PORT"] = str(db_port)
os.environ["DB_USER"] = db_user
os.environ["DB_PASSWORD"] = db_password
os.environ["DB_NAME"] = db_name
os.environ["REDIS_HOST"] = str(redis_host)
os.environ["REDIS_PORT"] = str(redis_port)
os.environ["REDIS_PASSWORD"] = redis_password
os.environ["REDIS_DB"] = str(redis_db)
os.environ["REDIS_ENABLED"] = "true" if redis_enabled else "false"

try:
    import uvicorn
except ImportError:
    print("=" * 50)
    print("❌ 错误：未找到 uvicorn 模块")
    print("=" * 50)
    print("请先安装依赖：")
    print("  1. 激活虚拟环境")
    print("  2. 运行: pip install -r requirements.txt")
    print("=" * 50)
    sys.exit(1)

# 导入数据库诊断工具
try:
    from scripts.utils.database_check import diagnose_database_connection
except ImportError:
    print("=" * 50)
    print("❌ 错误：无法导入数据库诊断工具")
    print("=" * 50)
    print("请确认 scripts/utils/database_check.py 文件存在")
    sys.exit(1)

# 导入 Redis 诊断工具
try:
    from scripts.utils.redis_check import diagnose_redis_connection
except ImportError:
    # Redis 是可选的，如果导入失败也不影响启动
    diagnose_redis_connection = None


def get_local_ip():
    """获取本机内网IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


if __name__ == "__main__":
    # 在启动应用前，先进行数据库环境检查
    print("=" * 50)
    print("    数据库环境检查")
    print("=" * 50)
    print()
    print("正在检查数据库连接...")
    print()
    
    diagnosis = diagnose_database_connection(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name
    )
    
    # 显示服务状态
    if diagnosis['service_status'] == 'RUNNING':
        print(f"[✓] MySQL 服务正在运行: {diagnosis['service_name']}")
    elif diagnosis['service_status'] == 'STOPPED':
        print(f"[✗] MySQL 服务未运行: {diagnosis['service_name']}")
        print()
        print("=" * 50)
        print("❌ 数据库环境检查失败")
        print("=" * 50)
        print()
        print("请先启动 MySQL 服务：")
        print(f"  1. 以管理员身份运行: net start \"{diagnosis['service_name']}\"")
        print("  2. 或通过服务管理器启动（Win+R -> services.msc）")
        print()
        print("=" * 50)
        sys.exit(1)
    else:
        print("[✗] 未检测到 MySQL 服务")
        print()
        print("=" * 50)
        print("❌ 数据库环境检查失败")
        print("=" * 50)
        print()
        print("请确认：")
        print("  1. MySQL 已安装")
        print("  2. MySQL 服务已启动")
        print()
        print("=" * 50)
        sys.exit(1)
    
    print()
    
    # 显示连接测试结果
    if diagnosis['connection_success']:
        print("[✓] 数据库连接测试成功")
        print()
    else:
        print(f"[✗] 数据库连接测试失败: {diagnosis['error_message']}")
        print()
        print("=" * 50)
        print("❌ 数据库环境检查失败")
        print("=" * 50)
        print()
        if diagnosis['recommendations']:
            print("建议操作：")
            for i, rec in enumerate(diagnosis['recommendations'], 1):
                print(f"  {i}. {rec}")
        print()
        print("=" * 50)
        sys.exit(1)
    
    print("=" * 50)
    print()
    
    # Redis 环境检查（总是检查，如果可用则自动启动）
    if diagnose_redis_connection:
        print("=" * 50)
        print("    Redis 环境检查")
        print("=" * 50)
        print()
        print("正在检查 Redis 连接...")
        print()
        
        redis_diagnosis = diagnose_redis_connection(
            host=redis_host,
            port=redis_port,
            password=redis_password,  # 传递字符串（空字符串或非空字符串），函数内部会处理
            db=redis_db,
            auto_start=True  # 自动启动 Redis（如果未运行）
        )
        
        if redis_diagnosis["connection_success"]:
            print("[✓] Redis 连接测试成功")
            if redis_diagnosis.get("auto_started"):
                print("[✓] Redis 服务已自动启动")
            if redis_diagnosis.get("redis_version"):
                print(f"   Redis 版本: {redis_diagnosis.get('redis_version')}")
            if not redis_enabled:
                print("   提示: 如需启用 Redis 功能，请设置环境变量 REDIS_ENABLED=true")
            print()
        else:
            print(f"[✗] Redis 连接测试失败: {redis_diagnosis.get('error_message', '未知错误')}")
            print()
            if redis_enabled:
                print("=" * 50)
                print("⚠️  Redis 环境检查失败（但服务器将继续启动）")
                print("=" * 50)
                print()
                if redis_diagnosis.get("recommendations"):
                    print("建议操作：")
                    for i, rec in enumerate(redis_diagnosis["recommendations"], 1):
                        print(f"  {i}. {rec}")
                print()
            else:
                print("   注意: Redis 未启用，服务器将在没有 Redis 的情况下运行")
                print("   如需启用 Redis，请在 .env 文件中设置 REDIS_ENABLED=true")
                print("   配置文件示例: .env.example")
                print()
        
        print("=" * 50)
        print()
    
    # 环境检查通过，启动服务器
    local_ip = get_local_ip()
    
    print("=" * 50)
    print("🚀 文件闪传系统API服务器")
    print("=" * 50)
    print("📊 数据库配置：")
    print(f"   • 主机: {db_host}")
    print(f"   • 端口: {db_port}")
    print(f"   • 用户: {db_user}")
    print(f"   • 数据库: {db_name}")
    if redis_enabled:
        print("")
        print("📦 Redis 配置：")
        print(f"   • 主机: {redis_host}")
        print(f"   • 端口: {redis_port}")
        print(f"   • 数据库: {redis_db}")
        print(f"   • 状态: 已启用")
    print("")
    print("📱 你自己访问：")
    print(f"   • http://127.0.0.1:8000 (最快)")
    print(f"   • http://localhost:8000")
    print(f"   • http://{local_ip}:8000")
    print("")
    print("👥 前端组访问：")
    print(f"   • http://{local_ip}:8000")
    print(f"   • 文档: http://{local_ip}:8000/docs")
    print(f"   • 健康检查: http://{local_ip}:8000/health")
    print("")
    print("⚠️  注意：")
    print("   • 保持电脑开机才能访问")
    print("   • 换网络后IP会变")
    print("   • 按 Ctrl+C 停止服务器")
    print("=" * 50)
    print()
    
    # 检查是否有SSL证书
    from pathlib import Path
    cert_dir = Path(project_root) / "certs"
    cert_file = cert_dir / "server.crt"
    key_file = cert_dir / "server.key"
    
    use_https = False
    ssl_keyfile = None
    ssl_certfile = None
    
    if cert_file.exists() and key_file.exists():
        use_https = True
        ssl_certfile = str(cert_file)
        ssl_keyfile = str(key_file)
        print("🔒 检测到SSL证书，将使用HTTPS模式")
        print(f"   证书: {ssl_certfile}")
        print(f"   私钥: {ssl_keyfile}")
        print()
        print("⚠️  注意: 这是自签名证书，浏览器会显示安全警告")
        print("   点击'高级' -> '继续访问'（不安全网站）即可")
        print()
        print("📱 HTTPS 访问地址：")
        print(f"   • https://127.0.0.1:8000")
        print(f"   • https://localhost:8000")
        print(f"   • https://{local_ip}:8000")
        print()
    else:
        print("⚠️  未检测到SSL证书，使用HTTP模式")
        print("   如果使用IP地址访问，加密功能可能无法使用")
        print("   建议运行 scripts\\setup\\generate_ssl_cert\\generate_ssl_cert.bat 生成证书")
        print()
    
    try:
        import logging
        import re
        
        # 配置日志过滤器，过滤频繁请求的日志
        # 需要在 uvicorn 启动之前配置，并且要确保应用到所有相关的 logger
        class AccessLogFilter(logging.Filter):
            """过滤频繁请求的访问日志"""
            # 需要过滤的路径模式（匹配完整的日志消息）
            FILTERED_PATTERNS = [
                r'/status',  # 状态查询接口
                r'/health',  # 健康检查
                r'/upload-chunk',  # 文件块上传接口
                r'/download-chunk',  # 文件块下载接口
            ]
            
            def filter(self, record):
                # 检查日志消息是否包含被过滤的路径
                # uvicorn 的访问日志格式类似: "192.168.43.160:63503 - "GET /api/v1/codes/G8QQ5P/status HTTP/1.1" 200 OK"
                message = record.getMessage()
                for pattern in self.FILTERED_PATTERNS:
                    if re.search(pattern, message):
                        return False  # 过滤掉这条日志
                return True  # 保留其他日志
        
        # 提前配置日志过滤器（在 uvicorn 启动之前）
        # 需要应用到所有 uvicorn 相关的 logger
        access_filter = AccessLogFilter()
        
        # 配置 uvicorn.access logger
        uvicorn_access_logger = logging.getLogger("uvicorn.access")
        uvicorn_access_logger.addFilter(access_filter)
        
        # 也配置 uvicorn logger（以防万一）
        uvicorn_logger = logging.getLogger("uvicorn")
        if not any(isinstance(f, AccessLogFilter) for f in uvicorn_logger.filters):
            uvicorn_logger.addFilter(access_filter)
        
        # 确保过滤器被正确添加
        print("✓ 日志过滤器已配置：将过滤状态查询、上传/下载块等频繁请求的日志")
        print()
        
        uvicorn_config = {
            "app": "app.main:app",
            "host": "0.0.0.0",
            "port": 8000,
            "reload": True,
            "log_level": "info",
            "access_log": True  # 保持访问日志开启，但通过过滤器过滤
        }
        
        if use_https:
            uvicorn_config["ssl_keyfile"] = ssl_keyfile
            uvicorn_config["ssl_certfile"] = ssl_certfile
        
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        print("\n" + "=" * 50)
        print("👋 服务器已停止")
        print("=" * 50)
    except Exception as e:
        print("\n" + "=" * 50)
        print(f"❌ 启动失败: {e}")
        print("=" * 50)
        print("请检查：")
        print("  1. 虚拟环境是否已激活")
        print("  2. 依赖是否已安装 (pip install -r requirements.txt)")
        print("  3. 数据库是否已配置")
        print("=" * 50)
        sys.exit(1)

