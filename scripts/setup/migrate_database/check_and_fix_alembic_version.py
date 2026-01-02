#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查并修复 Alembic 版本不匹配问题

当迁移文件被删除或重新创建时，数据库中的 alembic_version 表可能还记录着旧的版本号，
导致 Alembic 无法找到对应的迁移文件。此脚本可以检测并修复这种情况。
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
# __file__ = scripts/setup/migrate_database/check_and_fix_alembic_version.py
# parent = scripts/setup/migrate_database
# parent.parent = scripts/setup
# parent.parent.parent = scripts
# parent.parent.parent.parent = 项目根目录
script_file = Path(__file__).resolve()
project_root = script_file.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from sqlalchemy import create_engine, text
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
except ImportError as e:
    print(f"ERROR|导入失败: {e}")
    print("请确保已安装依赖: pip install sqlalchemy alembic pymysql")
    sys.exit(1)


def get_alembic_config():
    """获取 Alembic 配置"""
    alembic_ini_path = project_root / "alembic.ini"
    if not alembic_ini_path.exists():
        print(f"ERROR|未找到 alembic.ini 文件: {alembic_ini_path}")
        sys.exit(1)
    
    config = Config(str(alembic_ini_path))
    return config


def get_database_version(engine):
    """获取数据库中的当前版本号"""
    try:
        with engine.connect() as connection:
            # 检查 alembic_version 表是否存在
            result = connection.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE() 
                AND table_name = 'alembic_version'
            """))
            table_exists = result.fetchone()[0] > 0
            
            if not table_exists:
                return None, "表不存在"
            
            # 获取当前版本号
            result = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            row = result.fetchone()
            if row:
                return row[0], "正常"
            else:
                return None, "表为空"
    except Exception as e:
        return None, f"错误: {str(e)}"


def get_available_versions(script_dir):
    """获取所有可用的迁移版本号"""
    versions = []
    try:
        # 获取所有版本（包括分支）
        for script in script_dir.walk_revisions():
            versions.append(script.revision)
        # 如果没有找到版本，尝试获取 head
        if not versions:
            try:
                head = script_dir.get_current_head()
                if head:
                    versions.append(head)
            except:
                pass
    except Exception as e:
        print(f"WARNING|获取迁移版本失败: {e}")
    return versions


def fix_version_mismatch(engine, target_version=None):
    """修复版本不匹配问题"""
    try:
        with engine.connect() as connection:
            if target_version:
                # 更新到指定版本
                connection.execute(text(f"UPDATE alembic_version SET version_num = '{target_version}'"))
                connection.commit()
                return f"已更新到版本: {target_version}"
            else:
                # 清空版本表（标记为未初始化）
                connection.execute(text("DELETE FROM alembic_version"))
                connection.commit()
                return "已清空版本表，将从头开始迁移"
    except Exception as e:
        return f"修复失败: {str(e)}"


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python check_and_fix_alembic_version.py <action> [options]")
        print("  action: check|fix|auto-fix")
        print("  options: --version=<version> (仅用于 fix 操作)")
        sys.exit(1)
    
    action = sys.argv[1]
    
    # 获取配置
    config = get_alembic_config()
    database_url = config.get_main_option("sqlalchemy.url")
    
    if not database_url:
        print("ERROR|未找到数据库连接配置")
        sys.exit(1)
    
    # 创建数据库引擎
    try:
        engine = create_engine(database_url)
    except Exception as e:
        print(f"ERROR|创建数据库连接失败: {e}")
        sys.exit(1)
    
    # 获取脚本目录
    script_dir = ScriptDirectory.from_config(config)
    
    # 获取数据库中的版本号
    db_version, db_status = get_database_version(engine)
    
    # 获取所有可用的版本号
    available_versions = get_available_versions(script_dir)
    
    if action == "check":
        # 检查模式：只检查，不修复
        print(f"STATUS|{db_status}")
        if db_version:
            print(f"DB_VERSION|{db_version}")
            if db_version in available_versions:
                print("MATCH|true")
                print("数据库版本与迁移文件匹配")
            else:
                print("MATCH|false")
                print(f"警告: 数据库版本 {db_version} 不在可用的迁移文件中")
                print(f"可用的版本: {', '.join(available_versions) if available_versions else '无'}")
        else:
            print("DB_VERSION|无")
            print("MATCH|unknown")
            print("数据库中没有版本记录（可能是新数据库）")
    
    elif action == "fix":
        # 修复模式：需要指定版本号
        if len(sys.argv) < 3 or not sys.argv[2].startswith("--version="):
            print("ERROR|修复操作需要指定版本号: --version=<version>")
            print(f"可用的版本: {', '.join(available_versions) if available_versions else '无'}")
            sys.exit(1)
        
        target_version = sys.argv[2].split("=", 1)[1]
        result = fix_version_mismatch(engine, target_version)
        print(f"RESULT|{result}")
    
    elif action == "auto-fix":
        # 自动修复模式：检测并自动修复
        if db_version and db_version not in available_versions:
            print(f"STATUS|版本不匹配")
            print(f"DB_VERSION|{db_version}")
            print(f"AVAILABLE_VERSIONS|{','.join(available_versions) if available_versions else '无'}")
            
            # 如果有可用的版本，使用最新的版本
            if available_versions:
                # 获取 head 版本（最新的版本）
                try:
                    head_version = script_dir.get_current_head()
                    if head_version:
                        result = fix_version_mismatch(engine, head_version)
                        print(f"RESULT|{result}")
                        print(f"已自动修复: 更新到最新版本 {head_version}")
                    else:
                        # 如果无法获取 head，使用第一个可用版本
                        result = fix_version_mismatch(engine, available_versions[0])
                        print(f"RESULT|{result}")
                except Exception as e:
                    # 如果获取 head 失败，清空版本表（让 Alembic 从头开始）
                    result = fix_version_mismatch(engine, None)
                    print(f"RESULT|{result}")
                    print(f"WARNING|无法获取 head 版本: {e}，已清空版本表")
            else:
                # 没有可用的迁移文件，清空版本表
                result = fix_version_mismatch(engine, None)
                print(f"RESULT|{result}")
        elif db_version is None:
            print("STATUS|数据库中没有版本记录（正常，将从头开始迁移）")
        else:
            print("STATUS|版本匹配，无需修复")
            print(f"DB_VERSION|{db_version}")
    
    else:
        print(f"ERROR|未知操作: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()

