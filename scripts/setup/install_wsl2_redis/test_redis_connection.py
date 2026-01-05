#!/usr/bin/env python3
"""
QuickShare - Redis 连接测试脚本（Python）

用于测试从 Python 连接到 Redis 是否正常
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

try:
    import redis
except ImportError:
    print("❌ 错误: 未安装 redis 库")
    print("请运行: pip install redis")
    sys.exit(1)

def test_redis_connection():
    """测试 Redis 连接"""
    print("=" * 50)
    print("QuickShare - Redis 连接测试（Python）")
    print("=" * 50)
    print()
    
    # Redis 配置
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_password = os.getenv("REDIS_PASSWORD", None)
    redis_db = int(os.getenv("REDIS_DB", "0"))
    
    print(f"连接配置:")
    print(f"  - 地址: {redis_host}")
    print(f"  - 端口: {redis_port}")
    print(f"  - 数据库: {redis_db}")
    print(f"  - 密码: {'已设置' if redis_password else '无'}")
    print()
    
    try:
        # 创建 Redis 连接
        print("[1/3] 正在连接 Redis...")
        r = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True,
            socket_connect_timeout=5
        )
        
        # 测试连接
        print("[2/3] 测试连接...")
        result = r.ping()
        if result:
            print("✓ Redis 连接成功")
        else:
            print("❌ Redis 连接失败: ping 返回 False")
            return False
        
        # 测试读写
        print("[3/3] 测试读写操作...")
        test_key = "quick_share_test_key"
        test_value = "test_value_123"
        
        r.set(test_key, test_value, ex=10)  # 10秒后过期
        retrieved_value = r.get(test_key)
        
        if retrieved_value == test_value:
            print("✓ Redis 读写测试成功")
            r.delete(test_key)  # 清理测试数据
        else:
            print(f"❌ Redis 读写测试失败: 期望 '{test_value}', 得到 '{retrieved_value}'")
            return False
        
        # 获取服务器信息
        print()
        print("Redis 服务器信息:")
        info = r.info()
        print(f"  - Redis 版本: {info.get('redis_version', 'unknown')}")
        print(f"  - 运行模式: {info.get('redis_mode', 'unknown')}")
        print(f"  - 已用内存: {info.get('used_memory_human', 'unknown')}")
        print(f"  - 连接客户端数: {info.get('connected_clients', 'unknown')}")
        print(f"  - 数据库大小: {r.dbsize()} 个键")
        
        print()
        print("=" * 50)
        print("✓ Redis 连接测试通过！")
        print("=" * 50)
        return True
        
    except redis.ConnectionError as e:
        print(f"❌ Redis 连接错误: {e}")
        print()
        print("请检查：")
        print("  1. Redis 服务是否正在运行")
        print("  2. Redis 地址和端口是否正确")
        print("  3. 防火墙是否阻止了连接")
        print()
        print("启动 Redis 服务：")
        print("  wsl sudo service redis-server start")
        return False
        
    except redis.AuthenticationError as e:
        print(f"❌ Redis 认证错误: {e}")
        print()
        print("请检查 Redis 密码是否正确")
        return False
        
    except Exception as e:
        print(f"❌ 发生错误: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_redis_connection()
    sys.exit(0 if success else 1)

