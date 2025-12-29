#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置 Alembic 脚本
自动配置 alembic.ini 文件中的数据库连接信息
"""
import sys
import re
from pathlib import Path
from urllib.parse import quote_plus


def configure_alembic_ini(project_root, db_user, db_password, db_host, db_port, db_name):
    """
    配置 alembic.ini 文件中的数据库连接字符串
    
    Args:
        project_root: 项目根目录路径
        db_user: 数据库用户名
        db_password: 数据库密码
        db_host: 数据库主机
        db_port: 数据库端口
        db_name: 数据库名称
    
    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        alembic_ini_path = Path(project_root) / 'alembic.ini'
        
        if not alembic_ini_path.exists():
            print(f"[错误] 未找到 alembic.ini 文件: {alembic_ini_path}")
            return False
        
        # 读取文件内容
        with open(alembic_ini_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 对用户名和密码进行 URL 编码（处理特殊字符）
        encoded_user = quote_plus(db_user)
        encoded_password = quote_plus(db_password)
        
        # 构建新的数据库连接字符串
        new_url = f"sqlalchemy.url = mysql+pymysql://{encoded_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
        
        # 使用正则表达式替换数据库连接字符串
        # 匹配 sqlalchemy.url = mysql+pymysql://... 到行尾的所有内容
        pattern = r'sqlalchemy\.url\s*=\s*mysql\+pymysql://[^\r\n]*'
        new_content = re.sub(pattern, new_url, content)
        
        # 如果替换失败（没有找到匹配），尝试逐行查找和替换
        if new_content == content:
            # 查找 sqlalchemy.url 行所在位置
            lines = content.split('\n')
            for i, line in enumerate(lines):
                # 匹配包含 sqlalchemy.url 和 mysql+pymysql 的行
                if re.search(r'sqlalchemy\.url\s*=\s*mysql\+pymysql://', line):
                    lines[i] = new_url
                    new_content = '\n'.join(lines)
                    break
            else:
                print("[警告] 未找到 sqlalchemy.url 配置行，尝试在文件末尾添加")
                new_content = content.rstrip() + '\n' + new_url + '\n'
        
        # 写回文件
        with open(alembic_ini_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"[成功] alembic.ini 配置已更新")
        return True
        
    except Exception as e:
        print(f"[错误] 配置 alembic.ini 失败: {e}")
        return False


def main():
    """主函数"""
    if len(sys.argv) != 7:
        print("用法: configure_alembic.py <project_root> <db_user> <db_password> <db_host> <db_port> <db_name>")
        print(f"[调试] 实际接收到的参数数量: {len(sys.argv)}")
        print(f"[调试] 参数列表: {sys.argv}")
        sys.exit(1)
    
    project_root = sys.argv[1]
    db_user = sys.argv[2]
    db_password = sys.argv[3]
    db_host = sys.argv[4]
    db_port = sys.argv[5]
    db_name = sys.argv[6]
    
    success = configure_alembic_ini(project_root, db_user, db_password, db_host, db_port, db_name)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

