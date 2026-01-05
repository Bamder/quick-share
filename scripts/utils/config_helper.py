"""
配置助手：交互式配置数据库和 Redis
"""
import os
import sys
from pathlib import Path


def load_env_file(env_path):
    """加载 .env 文件"""
    config = {}
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    return config


def save_env_file(env_path, config):
    """保存配置到 .env 文件"""
    # 读取现有文件（保留注释和现有配置）
    existing_config = {}
    other_lines = []
    
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line_stripped = line.strip()
                if line_stripped and not line_stripped.startswith('#') and '=' in line_stripped:
                    key = line_stripped.split('=', 1)[0].strip()
                    value = line_stripped.split('=', 1)[1].strip()
                    existing_config[key] = value
                    # 保留原始行（包括注释和格式）
                    other_lines.append((key, line))
                else:
                    other_lines.append((None, line))
    
    # 合并配置（新配置优先）
    final_config = {**existing_config, **config}
    
    # 写入文件
    with open(env_path, 'w', encoding='utf-8') as f:
        # 先写入注释和其他行
        written_keys = set()
        for key, line in other_lines:
            if key is None:
                f.write(line)
            elif key in final_config:
                f.write(f"{key}={final_config[key]}\n")
                written_keys.add(key)
            else:
                f.write(line)
                if key:
                    written_keys.add(key)
        
        # 添加新配置（如果不存在于文件中）
        for key, value in final_config.items():
            if key not in written_keys:
                f.write(f"{key}={value}\n")


def interactive_db_config():
    """交互式配置数据库"""
    print("\n" + "=" * 50)
    print("    数据库配置")
    print("=" * 50)
    print()
    
    # 检查是否存在 .env 文件
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / ".env"
    env_example_path = project_root / ".env.example"
    
    has_env = env_path.exists()
    has_example = env_example_path.exists()
    
    if has_env or has_example:
        print("检测到配置文件：")
        if has_env:
            print(f"  ✓ .env 文件存在")
        if has_example:
            print(f"  ✓ .env.example 文件存在")
        print()
        choice = input("是否从配置文件导入数据库配置？(Y/N，默认: Y): ").strip().upper()
        if not choice:
            choice = "Y"
        
        if choice == "Y":
            # 从配置文件读取
            if has_env:
                config = load_env_file(env_path)
            elif has_example:
                config = load_env_file(env_example_path)
            else:
                config = {}
            
            db_host = config.get("DB_HOST", "localhost")
            db_port = config.get("DB_PORT", "3306")
            db_user = config.get("DB_USER", "root")
            db_password = config.get("DB_PASSWORD", "")
            db_name = config.get("DB_NAME", "quick_share_datagrip")
            
            print(f"\n从配置文件读取的数据库配置：")
            print(f"  主机: {db_host}")
            print(f"  端口: {db_port}")
            print(f"  用户: {db_user}")
            print(f"  数据库: {db_name}")
            print()
            
            use_config = input("是否使用此配置？(Y/N，默认: Y): ").strip().upper()
            if not use_config:
                use_config = "Y"
            
            if use_config == "Y":
                return {
                    "DB_HOST": db_host,
                    "DB_PORT": db_port,
                    "DB_USER": db_user,
                    "DB_PASSWORD": db_password,
                    "DB_NAME": db_name
                }
    
    # 手动配置
    print("\n手动配置数据库：")
    print()
    
    db_host = input("数据库主机 (默认: localhost): ").strip() or "localhost"
    db_port = input("数据库端口 (默认: 3306): ").strip() or "3306"
    db_user = input("数据库用户 (默认: root): ").strip() or "root"
    db_password = input("数据库密码 (默认: 空): ").strip()
    db_name = input("数据库名称 (默认: quick_share_datagrip): ").strip() or "quick_share_datagrip"
    
    config = {
        "DB_HOST": db_host,
        "DB_PORT": db_port,
        "DB_USER": db_user,
        "DB_PASSWORD": db_password,
        "DB_NAME": db_name
    }
    
    # 询问是否保存到配置文件
    if has_env or has_example:
        save_choice = input("\n是否保存此配置到 .env 文件？(Y/N，默认: Y): ").strip().upper()
        if not save_choice:
            save_choice = "Y"
        
        if save_choice == "Y":
            save_env_file(env_path, config)
            print(f"✓ 配置已保存到 {env_path}")
    
    return config


def interactive_redis_config():
    """交互式配置 Redis"""
    print("\n" + "=" * 50)
    print("    Redis 配置")
    print("=" * 50)
    print()
    
    # 检查是否存在 .env 文件
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / ".env"
    env_example_path = project_root / ".env.example"
    
    has_env = env_path.exists()
    has_example = env_example_path.exists()
    
    if has_env or has_example:
        print("检测到配置文件：")
        if has_env:
            print(f"  ✓ .env 文件存在")
        if has_example:
            print(f"  ✓ .env.example 文件存在")
        print()
        choice = input("是否从配置文件导入 Redis 配置？(Y/N，默认: Y): ").strip().upper()
        if not choice:
            choice = "Y"
        
        if choice == "Y":
            # 从配置文件读取
            if has_env:
                config = load_env_file(env_path)
            elif has_example:
                config = load_env_file(env_example_path)
            else:
                config = {}
            
            redis_enabled = config.get("REDIS_ENABLED", "false").lower() == "true"
            redis_host = config.get("REDIS_HOST", "localhost")
            redis_port = config.get("REDIS_PORT", "6379")
            redis_password = config.get("REDIS_PASSWORD", "")
            redis_db = config.get("REDIS_DB", "0")
            
            print(f"\n从配置文件读取的 Redis 配置：")
            print(f"  启用状态: {'已启用' if redis_enabled else '未启用'}")
            print(f"  主机: {redis_host}")
            print(f"  端口: {redis_port}")
            print(f"  数据库: {redis_db}")
            print()
            
            use_config = input("是否使用此配置？(Y/N，默认: Y): ").strip().upper()
            if not use_config:
                use_config = "Y"
            
            if use_config == "Y":
                return {
                    "REDIS_ENABLED": "true" if redis_enabled else "false",
                    "REDIS_HOST": redis_host,
                    "REDIS_PORT": redis_port,
                    "REDIS_PASSWORD": redis_password,
                    "REDIS_DB": redis_db
                }
    
    # 手动配置
    print("\n手动配置 Redis：")
    print()
    
    # 首先询问是否启用 Redis
    enable_choice = input("是否启用 Redis？(Y/N，默认: N): ").strip().upper()
    if not enable_choice:
        enable_choice = "N"
    
    redis_enabled = enable_choice == "Y"
    
    if redis_enabled:
        redis_host = input("Redis 主机 (默认: localhost): ").strip() or "localhost"
        redis_port = input("Redis 端口 (默认: 6379): ").strip() or "6379"
        redis_password = input("Redis 密码 (默认: 空): ").strip()
        redis_db = input("Redis 数据库 (默认: 0): ").strip() or "0"
    else:
        # 即使不启用，也设置默认值
        redis_host = "localhost"
        redis_port = "6379"
        redis_password = ""
        redis_db = "0"
    
    config = {
        "REDIS_ENABLED": "true" if redis_enabled else "false",
        "REDIS_HOST": redis_host,
        "REDIS_PORT": redis_port,
        "REDIS_PASSWORD": redis_password,
        "REDIS_DB": redis_db
    }
    
    # 询问是否保存到配置文件
    if has_env or has_example:
        save_choice = input("\n是否保存此配置到 .env 文件？(Y/N，默认: Y): ").strip().upper()
        if not save_choice:
            save_choice = "Y"
        
        if save_choice == "Y":
            save_env_file(env_path, config)
            print(f"✓ 配置已保存到 {env_path}")
    
    return config


if __name__ == "__main__":
    try:
        # 交互式配置数据库
        db_config = interactive_db_config()
        
        # 交互式配置 Redis
        redis_config = interactive_redis_config()
        
        # 合并配置并保存到 .env 文件
        project_root = Path(__file__).parent.parent.parent
        env_path = project_root / ".env"
        
        all_config = {**db_config, **redis_config}
        save_env_file(env_path, all_config)
        
        print("\n" + "=" * 50)
        print("✓ 配置完成！")
        print("=" * 50)
        print(f"\n配置已保存到: {env_path}")
        print("\n数据库配置：")
        print(f"  主机: {db_config.get('DB_HOST')}")
        print(f"  端口: {db_config.get('DB_PORT')}")
        print(f"  用户: {db_config.get('DB_USER')}")
        print(f"  数据库: {db_config.get('DB_NAME')}")
        print("\nRedis 配置：")
        print(f"  启用: {'是' if redis_config.get('REDIS_ENABLED') == 'true' else '否'}")
        if redis_config.get('REDIS_ENABLED') == 'true':
            print(f"  主机: {redis_config.get('REDIS_HOST')}")
            print(f"  端口: {redis_config.get('REDIS_PORT')}")
            print(f"  数据库: {redis_config.get('REDIS_DB')}")
        print()
        
    except KeyboardInterrupt:
        print("\n\n配置已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n配置失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

