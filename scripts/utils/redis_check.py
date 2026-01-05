"""
Redis 连接检查和启动工具
"""
import subprocess
import sys
import time
import os
import shlex

try:
    import redis
except ImportError:
    redis = None


def check_wsl_available():
    """检查 WSL 是否可用"""
    try:
        result = subprocess.run(
            ["wsl", "--status"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',  # 忽略编码错误
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def check_wsl_running():
    """检查 WSL 是否正在运行"""
    try:
        # 尝试执行一个简单的 WSL 命令来检查是否运行
        result = subprocess.run(
            ["wsl", "echo", "test"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def start_wsl2():
    """启动 WSL2（如果未运行）"""
    try:
        print("  正在检查 WSL2 状态...")
        if check_wsl_running():
            print("  ✓ WSL2 正在运行")
            return True
        
        print("  WSL2 未运行，正在启动...")
        # 尝试启动 WSL2（通过执行一个命令来触发启动）
        result = subprocess.run(
            ["wsl", "echo", "WSL2 starting"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=15  # WSL2 启动可能需要一些时间
        )
        
        if result.returncode == 0:
            print("  ✓ WSL2 已启动")
            time.sleep(2)  # 等待 WSL2 完全启动
            return True
        else:
            print("  ⚠️  WSL2 启动可能失败，继续尝试...")
            # 即使返回码不为 0，也可能已经启动（首次启动会有警告信息）
            time.sleep(3)
            return check_wsl_running()
    except subprocess.TimeoutExpired:
        print("  ⚠️  WSL2 启动超时，但可能已启动，继续尝试...")
        time.sleep(2)
        return check_wsl_running()
    except Exception as e:
        print(f"  ⚠️  WSL2 启动异常: {e}")
        return False


def check_redis_installed():
    """检查 Redis 是否已安装"""
    try:
        result = subprocess.run(
            ["wsl", "which", "redis-server"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=5
        )
        return result.returncode == 0 and result.stdout.strip()
    except:
        return False


def start_redis_via_wsl(password=None):
    """通过 WSL 启动 Redis 服务
    
    Args:
        password: Redis 密码（可选），如果提供则启动时临时设置密码
    """
    try:
        # 首先确保 WSL2 正在运行
        if not start_wsl2():
            print("  ❌ 无法启动 WSL2，请手动启动 WSL2 后再试")
            return False
        
        # 检查 Redis 是否已安装
        print("  正在检查 Redis 是否已安装...")
        if not check_redis_installed():
            print("  ❌ Redis 未安装")
            print("  请先运行安装脚本: scripts\\setup\\install_wsl2_redis\\install_wsl2_redis.bat")
            return False
        print("  ✓ Redis 已安装")
        
        # 尝试多种方式启动 Redis
        if password:
            print("  检测到 Redis 密码配置，使用临时密码模式启动...")
        else:
            print("  正在通过 WSL 启动 Redis 服务...")
        
        # 如果配置了密码，优先使用直接启动方式（可以临时设置密码）
        if password:
            print("  尝试直接启动 Redis 服务器（后台模式，临时设置密码）...")
            # 转义密码中的特殊字符，防止 shell 注入
            escaped_password = shlex.quote(password)
            redis_cmd = f"redis-server --requirepass {escaped_password} --daemonize yes"
            result = subprocess.run(
                ["wsl", "bash", "-c", redis_cmd],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=10
            )
            if result.returncode == 0:
                print("  ✓ Redis 服务器已启动（后台模式，已临时设置密码）")
                time.sleep(2)
                return True
            else:
                print("  ⚠️  使用密码启动失败，尝试其他方式...")
        
        # 方法1: 尝试使用 systemctl（不需要 sudo，如果配置了用户服务）
        result = subprocess.run(
            ["wsl", "systemctl", "--user", "start", "redis-server"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=10
        )
        if result.returncode == 0:
            print("  ✓ Redis 服务已启动（通过 systemctl --user）")
            if password:
                print("  ⚠️  注意: 使用 systemctl 启动，密码需要在 Redis 配置文件中设置")
            time.sleep(2)
            return True
        
        # 方法2: 尝试使用 systemctl（需要 sudo，但可能已配置无密码）
        result = subprocess.run(
            ["wsl", "sudo", "-n", "systemctl", "start", "redis-server"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=10
        )
        if result.returncode == 0:
            print("  ✓ Redis 服务已启动（通过 systemctl）")
            if password:
                print("  ⚠️  注意: 使用 systemctl 启动，密码需要在 Redis 配置文件中设置")
            time.sleep(2)
            return True
        
        # 方法3: 尝试直接启动 redis-server（作为后台进程，不需要 sudo）
        print("  尝试直接启动 Redis 服务器（后台模式）...")
        redis_cmd = "redis-server --daemonize yes"
        if password:
            # 转义密码中的特殊字符
            escaped_password = shlex.quote(password)
            redis_cmd = f"redis-server --requirepass {escaped_password} --daemonize yes"
        
        result = subprocess.run(
            ["wsl", "bash", "-c", redis_cmd],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=10
        )
        if result.returncode == 0:
            print("  ✓ Redis 服务器已启动（后台模式）")
            if password:
                print("  ✓ Redis 密码已临时设置")
            time.sleep(2)
            return True
        
        # 方法4: 最后尝试使用 service 命令（需要 sudo，但可能已配置无密码）
        result = subprocess.run(
            ["wsl", "sudo", "-n", "service", "redis-server", "start"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=10
        )
        if result.returncode == 0:
            print("  ✓ Redis 服务已启动（通过 service）")
            if password:
                print("  ⚠️  注意: 使用 service 启动，密码需要在 Redis 配置文件中设置")
            time.sleep(2)
            return True
        
        # 所有方法都失败
        print("  ❌ 无法自动启动 Redis 服务")
        print("  可能的原因：")
        print("    1. 需要 sudo 密码（无法交互式输入）")
        print("    2. Redis 服务配置问题")
        print("  解决方案：")
        if password:
            print("    1. 手动在 WSL2 中启动（带密码）:")
            print(f"       wsl redis-server --requirepass {password} --daemonize yes")
        else:
            print("    1. 手动在 WSL2 中启动:")
            print("       wsl sudo service redis-server start")
        print("    2. 或配置无密码 sudo（在 WSL2 中运行: sudo visudo）")
        print("       添加: 你的用户名 ALL=(ALL) NOPASSWD: /usr/sbin/service redis-server *")
        if not password:
            print("    3. 或直接启动 Redis（不需要 sudo）:")
            print("       wsl redis-server --daemonize yes")
        return False
        
    except subprocess.TimeoutExpired:
        print("  启动超时")
        if password:
            print(f"  提示: 可以手动启动 Redis（带密码）: wsl redis-server --requirepass {password} --daemonize yes")
        else:
            print("  提示: 可以手动启动 Redis: wsl sudo service redis-server start")
        return False
    except Exception as e:
        print(f"  启动异常: {e}")
        return False


def check_redis_connection(host="localhost", port=6379, password=None, db=0, timeout=5):
    """
    检查 Redis 连接
    
    Args:
        host: Redis 主机地址
        port: Redis 端口
        password: Redis 密码（可选）
        db: Redis 数据库编号
        timeout: 连接超时时间（秒）
    
    Returns:
        dict: 包含检查结果的字典
    """
    result = {
        "available": False,
        "running": False,
        "connection_success": False,
        "wsl_available": False,
        "error_message": None,
        "recommendations": []
    }
    
    # 检查 redis 库是否安装
    if redis is None:
        result["error_message"] = "redis 库未安装"
        result["recommendations"].append("运行: pip install redis")
        return result
    
    # 检查 WSL 是否可用（用于启动 Redis）
    result["wsl_available"] = check_wsl_available()
    
    # 尝试连接 Redis
    try:
        r = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password if password else None,
            socket_connect_timeout=timeout,
            decode_responses=True
        )
        
        # 测试连接
        r.ping()
        result["connection_success"] = True
        result["running"] = True
        result["available"] = True
        
        # 获取服务器信息
        try:
            info = r.info()
            result["redis_version"] = info.get("redis_version", "unknown")
            result["used_memory_human"] = info.get("used_memory_human", "unknown")
        except:
            pass
            
    except redis.ConnectionError as e:
        result["error_message"] = f"无法连接到 Redis: {str(e)}"
        result["running"] = False
        
        # 如果 WSL 可用，尝试启动 Redis
        if result["wsl_available"]:
            result["recommendations"].append("尝试通过 WSL 启动 Redis 服务")
            result["recommendations"].append("运行: wsl sudo service redis-server start")
        else:
            result["recommendations"].append("请先安装 WSL2 和 Redis")
            result["recommendations"].append("运行: scripts\\setup\\install_wsl2_redis\\install_wsl2_redis.bat")
            
    except redis.AuthenticationError as e:
        result["error_message"] = f"Redis 认证失败: {str(e)}"
        result["recommendations"].append("请检查 Redis 密码配置")
        
    except Exception as e:
        result["error_message"] = f"未知错误: {str(e)}"
        result["recommendations"].append("请检查 Redis 配置和网络连接")
    
    return result


def diagnose_redis_connection(host=None, port=None, password=None, db=None, auto_start=False):
    """
    诊断 Redis 连接，如果未运行且 auto_start=True，则尝试自动启动
    
    Args:
        host: Redis 主机地址（默认从环境变量读取）
        port: Redis 端口（默认从环境变量读取）
        password: Redis 密码（默认从环境变量读取），如果提供非空字符串则启动时临时设置密码
        db: Redis 数据库编号（默认从环境变量读取）
        auto_start: 如果 Redis 未运行，是否尝试自动启动
    
    Returns:
        dict: 包含诊断结果的字典
    """
    # 从环境变量读取配置
    if host is None:
        host = os.getenv("REDIS_HOST", "localhost")
    if port is None:
        port = int(os.getenv("REDIS_PORT", "6379"))
    if password is None:
        password = os.getenv("REDIS_PASSWORD", "")
    if db is None:
        db = int(os.getenv("REDIS_DB", "0"))
    
    # 检查连接（如果密码为空字符串，则传递 None）
    diagnosis = check_redis_connection(host, port, password if password else None, db)
    
    # 如果连接失败且启用了自动启动，尝试启动 Redis
    if not diagnosis["connection_success"] and auto_start and diagnosis["wsl_available"]:
        print("  尝试自动启动 Redis...")
        # 传递密码参数（如果配置了非空密码，则临时设置）
        redis_password = password if password else None
        if start_redis_via_wsl(password=redis_password):
            # 重新检查连接
            time.sleep(1)
            diagnosis = check_redis_connection(host, port, password if password else None, db)
            if diagnosis["connection_success"]:
                diagnosis["auto_started"] = True
    
    return diagnosis

