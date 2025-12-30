#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检测和启动 MySQL 服务（命令行工具）
动态检测所有包含 MySQL 的服务（不硬编码任何服务名称）
支持自动启动服务（需要管理员权限）

这是一个命令行包装器，实际功能在 scripts.utils.database_check 中实现
"""
import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 添加 scripts 目录到 Python 路径
scripts_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

# 从统一工具模块导入函数
try:
    from scripts.utils.database_check import check_mysql_service, start_mysql_service
except ImportError:
    print("Error: 无法导入数据库检查工具", file=sys.stderr)
    print("请确认 scripts/utils/database_check.py 文件存在", file=sys.stderr)
    sys.exit(1)


def main():
    """主函数，支持命令行参数"""
    # 检查是否需要启动服务
    auto_start = len(sys.argv) > 1 and sys.argv[1] == '--auto-start'
    
    status, service_name = check_mysql_service()
    
    if not service_name:
        print("NOT_FOUND")
        sys.exit(1)
    
    if status == 'RUNNING':
        print(f"RUNNING|{service_name}")
        sys.exit(0)
    elif status == 'STOPPED':
        if auto_start:
            # 尝试自动启动
            print(f"尝试启动服务: {service_name}", file=sys.stderr)
            if start_mysql_service(service_name):
                # 再次检查状态
                new_status, _ = check_mysql_service()
                if new_status == 'RUNNING':
                    print(f"RUNNING|{service_name}")
                    sys.exit(0)
                else:
                    print(f"STOPPED|{service_name}|START_FAILED")
                    sys.exit(1)
            else:
                print(f"STOPPED|{service_name}|START_FAILED")
                sys.exit(1)
        else:
            print(f"STOPPED|{service_name}")
            sys.exit(0)
    else:
        print("NOT_FOUND")
        sys.exit(1)


if __name__ == '__main__':
    main()

