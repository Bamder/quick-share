#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库创建脚本
自动创建 MySQL 数据库，如果数据库已存在则跳过
"""
import sys
import pymysql
from pathlib import Path


def create_database(host='localhost', port=3306, user='root', password='', database='quick_share_datagrip'):
    """
    创建 MySQL 数据库
    
    Args:
        host: 数据库主机地址
        port: 数据库端口
        user: 数据库用户名
        password: 数据库密码
        database: 要创建的数据库名称
    
    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        # 先连接到 MySQL 服务器（不指定数据库）
        print(f"[信息] 正在连接到 MySQL 服务器 {host}:{port}...")
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # 检查数据库是否已存在
            cursor.execute("SHOW DATABASES LIKE %s", (database,))
            exists = cursor.fetchone()
            
            if exists:
                print(f"[提示] 数据库 {database} 已存在，跳过创建步骤")
                print(f"[信息] 将继续执行数据库迁移（alembic upgrade head）")
            else:
                # 创建数据库
                print(f"[信息] 正在创建数据库 {database}...")
                cursor.execute(
                    f"CREATE DATABASE {database} DEFAULT CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                print(f"[成功] 数据库 {database} 创建成功")
                print(f"[信息] 将继续执行数据库迁移（alembic upgrade head）")
        
        connection.close()
        return True
        
    except pymysql.Error as e:
        print(f"[错误] MySQL 错误: {e}")
        return False
    except Exception as e:
        print(f"[错误] 数据库创建失败: {e}")
        return False


def main():
    """主函数，支持命令行参数"""
    # 从命令行参数获取配置，如果没有则使用默认值
    if len(sys.argv) >= 6:
        host = sys.argv[1]
        port = int(sys.argv[2])
        user = sys.argv[3]
        password = sys.argv[4]
        database = sys.argv[5]
    elif len(sys.argv) == 2:
        # 只提供密码的情况
        password = sys.argv[1]
        host = 'localhost'
        port = 3306
        user = 'root'
        database = 'quick_share_datagrip'
    else:
        # 交互式输入
        print("=" * 40)
        print("    数据库创建脚本")
        print("=" * 40)
        print()
        
        user = input("数据库用户名 (默认: root): ").strip() or 'root'
        password = input("数据库密码: ").strip()
        if not password:
            print("[错误] 密码不能为空")
            sys.exit(1)
        
        host = input("数据库主机 (默认: localhost): ").strip() or 'localhost'
        port_str = input("数据库端口 (默认: 3306): ").strip() or '3306'
        try:
            port = int(port_str)
        except ValueError:
            print("[错误] 端口必须是数字")
            sys.exit(1)
        
        database = input("数据库名称 (默认: quick_share_datagrip): ").strip() or 'quick_share_datagrip'
    
    success = create_database(host=host, port=port, user=user, password=password, database=database)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

