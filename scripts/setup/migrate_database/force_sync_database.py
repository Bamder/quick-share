#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增强版数据库结构强制同步工具（交互式优化）

支持功能：
1. 自动检测并同步到最新版本（默认）
2. 指定目标版本进行同步
3. 版本比较和差异报告
4. 迁移历史查看
5. 回退到指定版本
6. 交互式版本选择
7. 详细的日志和报告生成
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime
import warnings

# 添加项目根目录到 Python 路径
script_file = Path(__file__).resolve()
project_root = script_file.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from sqlalchemy import create_engine, text, inspect, MetaData, Table
    from sqlalchemy.exc import OperationalError, ProgrammingError
    from alembic.config import Config
    from alembic import command
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
except ImportError as e:
    print(f"ERROR|导入失败: {e}")
    print("请确保已安装依赖: pip install sqlalchemy alembic pymysql")
    sys.exit(1)

# 导入所有模型（确保模型已注册）
try:
    from app.models import Base
    from app.models.file import File
    from app.models.user import User
    from app.models.pickup_code import PickupCode
    from app.models.report import Report
except ImportError as e:
    print(f"ERROR|导入模型失败: {e}")
    print("请确保模型文件正确且项目路径配置正确")
    sys.exit(1)

# 全局配置
MODELS = [File, User, PickupCode, Report]


class DatabaseSyncTool:
    """数据库同步工具类"""
    
    def __init__(self, database_url: str, verbose: bool = True, quiet: bool = False):
        self.database_url = database_url
        self.verbose = verbose and not quiet
        self.quiet = quiet
        self.engine = create_engine(database_url)
        self.config = self._get_alembic_config()
        self.script_dir = ScriptDirectory.from_config(self.config)
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'database_url': database_url,
            'actions': [],
            'errors': [],
            'warnings': [],
            'changes': []
        }
    
    def _get_alembic_config(self) -> Config:
        """获取 Alembic 配置"""
        alembic_ini_path = project_root / "alembic.ini"
        if not alembic_ini_path.exists():
            raise FileNotFoundError(f"未找到 alembic.ini 文件: {alembic_ini_path}")
        return Config(str(alembic_ini_path))
    
    def _log(self, message: str, level: str = "INFO"):
        """记录日志"""
        if self.verbose:
            print(f"[{level}] {message}")
        self.report['actions'].append({
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        })
    
    def _error(self, message: str):
        """记录错误"""
        if not self.quiet:
            print(f"[ERROR] {message}")
        self.report['actions'].append({
            'timestamp': datetime.now().isoformat(),
            'level': 'ERROR',
            'message': message
        })
        self.report['errors'].append(message)
    
    def _warning(self, message: str):
        """记录警告"""
        if not self.quiet:
            print(f"[WARNING] {message}")
        self.report['actions'].append({
            'timestamp': datetime.now().isoformat(),
            'level': 'WARNING',
            'message': message
        })
        self.report['warnings'].append(message)
    
    def _print(self, message: str = ""):
        """普通输出（受 quiet 模式控制）"""
        if not self.quiet:
            print(message)
    
    def get_current_version(self) -> Optional[str]:
        """获取数据库当前版本"""
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                row = result.fetchone()
                return row[0] if row else None
        except Exception as e:
            # alembic_version 表可能不存在
            return None
    
    def get_head_version(self) -> Optional[str]:
        """获取最新的迁移版本（head）"""
        try:
            return self.script_dir.get_current_head()
        except Exception as e:
            self._warning(f"无法获取 head 版本: {e}")
            return None
    
    def get_all_versions(self) -> List[str]:
        """获取所有可用的迁移版本"""
        versions = []
        try:
            for script in self.script_dir.walk_revisions():
                if script.revision not in versions:
                    versions.append(script.revision)
        except Exception as e:
            self._warning(f"获取迁移版本失败: {e}")
        return versions
    
    def get_version_info(self, version: str) -> Optional[Dict]:
        """获取版本信息"""
        try:
            for script in self.script_dir.walk_revisions():
                if script.revision == version:
                    return {
                        'revision': script.revision,
                        'doc': script.doc or '无描述',
                        'down_revision': script.down_revision,
                        'branch_labels': script.branch_labels,
                    }
        except Exception as e:
            self._warning(f"获取版本信息失败: {e}")
        return None
    
    def list_versions(self) -> None:
        """列出所有可用版本"""
        current = self.get_current_version()
        head = self.get_head_version()
        all_versions = self.get_all_versions()
        
        # list_versions 命令应该总是显示输出，即使有 --quiet 参数
        print("\n" + "=" * 60)
        print("迁移版本列表")
        print("=" * 60)
        
        if current:
            marker = " (最新)" if current == head else ""
            print(f"当前版本: {current}{marker}")
        else:
            print("当前版本: 未初始化")
        
        if head:
            print(f"最新版本 (head): {head}")
        
        print(f"\n所有可用版本 ({len(all_versions)} 个):")
        print("-" * 60)
        
        for version in all_versions:
            info = self.get_version_info(version)
            marker = ""
            if version == current:
                marker = " <-- 当前"
            if version == head:
                marker += " (head)"
            
            doc = info['doc'] if info else "无描述"
            print(f"  {version[:12]}... {doc[:50]}{marker}")
        
        print()
    
    def compare_versions(self, version1: Optional[str] = None, version2: Optional[str] = None) -> Dict:
        """比较两个版本的差异"""
        v1 = version1 or self.get_current_version()
        v2 = version2 or self.get_head_version()
        
        if not v1 or not v2:
            result = {'error': '无法比较版本（缺少版本信息）'}
            # compare_versions 命令应该总是显示输出，即使有 --quiet 参数
            print("\n" + "=" * 60)
            print("版本比较结果")
            print("=" * 60)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print()
            return result
        
        if v1 == v2:
            result = {'message': '版本相同，无需比较', 'from_version': v1, 'to_version': v2}
            # compare_versions 命令应该总是显示输出，即使有 --quiet 参数
            print("\n" + "=" * 60)
            print("版本比较结果")
            print("=" * 60)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print()
            return result
        
        # 构建迁移链
        chain = []
        try:
            revisions = {}
            for script in self.script_dir.walk_revisions():
                revisions[script.revision] = {
                    'down_revision': script.down_revision if isinstance(script.down_revision, str) else script.down_revision[0] if script.down_revision else None,
                    'revision': script.revision
                }
            
            # 从当前版本开始，找到目标版本
            if v1 in revisions and v2 in revisions:
                current = v1
                while current and current != v2:
                    for rev, info in revisions.items():
                        if info['down_revision'] == current:
                            chain.append(rev)
                            current = rev
                            break
                    else:
                        break
        except Exception as e:
            self._warning(f"构建迁移链失败: {e}")
        
        result = {
            'from_version': v1,
            'to_version': v2,
            'migration_chain': chain,
            'steps': len(chain),
            'message': f'需要执行 {len(chain)} 个迁移步骤' if chain else '无法构建迁移链'
        }
        
        # compare_versions 命令应该总是显示输出，即使有 --quiet 参数
        print("\n" + "=" * 60)
        print("版本比较结果")
        print("=" * 60)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()
        
        return result
    
    def get_database_columns(self, table_name: str) -> Dict[str, Dict]:
        """获取数据库中表的列信息"""
        inspector = inspect(self.engine)
        
        if table_name not in inspector.get_table_names():
            return {}
        
        columns_info = {}
        columns = inspector.get_columns(table_name)
        
        for col in columns:
            col_info = {
                'type': str(col['type']),
                'nullable': col['nullable'],
                'default': col.get('default'),
                'primary_key': col.get('primary_key', False),
                'comment': col.get('comment'),
                'autoincrement': col.get('autoincrement', False),
            }
            columns_info[col['name']] = col_info
        
        return columns_info
    
    def sqlalchemy_type_to_mysql_type(self, sqlalchemy_type_str: str, nullable: bool = True) -> str:
        """将 SQLAlchemy 类型字符串转换为 MySQL 类型字符串"""
        type_str = str(sqlalchemy_type_str).upper()
        
        if 'INTEGER' in type_str or 'INT' in type_str:
            if 'BIG' in type_str:
                return 'BIGINT'
            return 'INTEGER'
        elif 'VARCHAR' in type_str or 'STRING' in type_str:
            import re
            match = re.search(r'\((\d+)\)', type_str)
            length = match.group(1) if match else '255'
            return f'VARCHAR({length})'
        elif 'TEXT' in type_str:
            return 'TEXT'
        elif 'BOOLEAN' in type_str or 'BOOL' in type_str:
            return 'BOOLEAN'
        elif 'DATETIME' in type_str:
            return 'DATETIME'
        elif 'ENUM' in type_str:
            import re
            match = re.search(r'ENUM\((.*?)\)', type_str, re.IGNORECASE)
            if match:
                return f"ENUM({match.group(1)})"
            return 'ENUM'
        else:
            return type_str
    
    def add_missing_column(self, table_name: str, column_name: str, 
                           column_type: str, nullable: bool = True, 
                           default: Optional[str] = None, comment: Optional[str] = None,
                           server_default: Optional[str] = None) -> bool:
        """添加缺失的列到表中"""
        try:
            mysql_type = self.sqlalchemy_type_to_mysql_type(column_type, nullable)
            
            alter_sql = f"ALTER TABLE `{table_name}` ADD COLUMN `{column_name}` {mysql_type}"
            
            if not nullable:
                alter_sql += " NOT NULL"
            
            if server_default is not None:
                alter_sql += f" DEFAULT {server_default}"
            elif default is not None:
                if isinstance(default, (str,)) and default.upper() in ('FALSE', 'TRUE'):
                    alter_sql += f" DEFAULT {default}"
                elif isinstance(default, (int, float)):
                    alter_sql += f" DEFAULT {default}"
                elif isinstance(default, str) and default.startswith("'") and default.endswith("'"):
                    alter_sql += f" DEFAULT {default}"
                else:
                    alter_sql += f" DEFAULT '{default}'"
            
            if comment:
                alter_sql += f" COMMENT '{comment.replace(chr(39), chr(39)+chr(39))}'"
            
            with self.engine.connect() as connection:
                connection.execute(text(alter_sql))
                connection.commit()
            
            self.report['changes'].append({
                'type': 'add_column',
                'table': table_name,
                'column': column_name,
                'success': True
            })
            
            return True
        except Exception as e:
            error_msg = f"添加列失败 {table_name}.{column_name}: {e}"
            self._error(error_msg)
            self.report['changes'].append({
                'type': 'add_column',
                'table': table_name,
                'column': column_name,
                'success': False,
                'error': str(e)
            })
            return False
    
    def check_and_fix_table_structure(self, model_class) -> Tuple[bool, List[str]]:
        """检查并修复表结构"""
        table_name = model_class.__tablename__
        self._log(f"检查表: {table_name}")
        
        db_columns = self.get_database_columns(table_name)
        
        if not db_columns:
            self._warning(f"表 {table_name} 不存在，需要运行迁移创建")
            return False, [f"表 {table_name} 不存在"]
        
        model_columns = {}
        for column in model_class.__table__.columns:
            model_columns[column.name] = {
                'type': str(column.type),
                'nullable': column.nullable,
                'default': column.default.arg if column.default else None,
                'comment': column.comment,
                'server_default': str(column.server_default) if column.server_default else None,
            }
        
        missing_columns = []
        fixed_columns = []
        
        for col_name, col_info in model_columns.items():
            if col_name not in db_columns:
                self._log(f"  发现缺失列: {col_name} ({col_info['type']})")
                missing_columns.append(col_name)
                
                server_default = None
                if col_info['server_default']:
                    import re
                    default_str = col_info['server_default']
                    if "'" in default_str:
                        match = re.search(r"'([^']+)'", default_str)
                        if match:
                            server_default = f"'{match.group(1)}'"
                    elif default_str.isdigit() or default_str.upper() in ('TRUE', 'FALSE'):
                        server_default = default_str.upper()
                
                success = self.add_missing_column(
                    table_name=table_name,
                    column_name=col_name,
                    column_type=col_info['type'],
                    nullable=col_info['nullable'],
                    default=col_info['default'],
                    comment=col_info['comment'],
                    server_default=server_default or (f"'{col_info['default']}'" if isinstance(col_info['default'], str) else str(col_info['default']) if col_info['default'] is not None else None)
                )
                
                if success:
                    self._log(f"  ✓ 已添加列: {col_name}")
                    fixed_columns.append(col_name)
                else:
                    self._log(f"  ✗ 添加列失败: {col_name}", "ERROR")
        
        if missing_columns:
            if len(fixed_columns) == len(missing_columns):
                return True, []
            else:
                return False, [f"表 {table_name} 中有 {len(missing_columns) - len(fixed_columns)} 个列添加失败"]
        
        return True, []
    
    def sync_structure(self) -> bool:
        """同步数据库结构到模型定义"""
        if not self.quiet:
            print("\n" + "=" * 60)
            print("第一步: 检查并修复表结构")
            print("=" * 60)
        
        all_success = True
        errors = []
        
        for model in MODELS:
            success, model_errors = self.check_and_fix_table_structure(model)
            if not success:
                all_success = False
                errors.extend(model_errors)
        
        return all_success
    
    def sync_version(self, target_version: Optional[str] = None) -> bool:
        """同步 Alembic 版本记录"""
        target = target_version or self.get_head_version()
        
        if not target:
            self._error("无法确定目标版本")
            return False
        
        current = self.get_current_version()
        
        if current == target:
            self._log(f"Alembic 版本已是最新: {target}")
            return True
        
        self._log(f"更新 Alembic 版本记录: {current or '未初始化'} -> {target}")
        
        try:
            with self.engine.connect() as connection:
                try:
                    connection.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
                except:
                    connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
                    connection.commit()
                
                if current:
                    connection.execute(text(f"UPDATE alembic_version SET version_num = '{target}'"))
                else:
                    connection.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{target}')"))
                connection.commit()
            
            self._log(f"✓ Alembic 版本已更新为: {target}")
            return True
        except Exception as e:
            self._error(f"更新 Alembic 版本失败: {e}")
            return False
    
    def run_migration(self, target_version: Optional[str] = None) -> bool:
        """运行 Alembic 迁移"""
        target = target_version or "head"
        
        self._log(f"运行 Alembic 迁移到: {target}")
        
        try:
            command.upgrade(self.config, target)
            self._log("✓ Alembic 迁移执行完成")
            return True
        except Exception as e:
            self._warning(f"Alembic 迁移执行失败（可能已是最新版本）: {e}")
            return False
    
    def force_sync(self, target_version: Optional[str] = None) -> bool:
        """强制同步到指定版本"""
        if not self.quiet:
            print("\n" + "=" * 60)
            print("数据库结构强制同步工具")
            print("=" * 60)
        
        # 测试连接
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            self._log("数据库连接正常")
        except Exception as e:
            self._error(f"数据库连接失败: {e}")
            return False
        
        # 显示当前状态
        current = self.get_current_version()
        head = self.get_head_version()
        target = target_version or head
        
        if not self.quiet:
            print(f"\n当前版本: {current or '未初始化'}")
            print(f"目标版本: {target or '未知'}")
            if target and target != head:
                print(f"最新版本: {head}")
            print()
        
        # 同步结构
        structure_ok = self.sync_structure()
        
        # 同步版本
        version_ok = self.sync_version(target)
        
        # 运行迁移
        migration_ok = self.run_migration(target)
        
        return structure_ok and version_ok
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """生成同步报告"""
        report_json = json.dumps(self.report, indent=2, ensure_ascii=False)
        
        if output_file:
            output_path = Path(output_file)
            output_path.write_text(report_json, encoding='utf-8')
            self._print(f"\n报告已保存到: {output_file}")
        
        return report_json
    
    def interactive_select_version(self) -> Optional[str]:
        """交互式选择版本"""
        self.list_versions()
        
        self._print("\n请选择目标版本:")
        self._print("  1. 使用最新版本 (head)")
        self._print("  2. 保持当前版本")
        self._print("  3. 手动输入版本号")
        self._print("  4. 取消")
        
        try:
            choice = input("\n请输入选项 (1-4): ").strip()
            
            if choice == "1":
                return self.get_head_version()
            elif choice == "2":
                return self.get_current_version()
            elif choice == "3":
                version = input("请输入版本号: ").strip()
                all_versions = self.get_all_versions()
                if version in all_versions:
                    return version
                else:
                    self._error(f"版本 {version} 不存在")
                    self._print(f"可用版本: {', '.join(all_versions[:5])}...")
                    return None
            else:
                return None
        except KeyboardInterrupt:
            self._print("\n\n操作已取消")
            return None
        except Exception as e:
            self._error(f"输入错误: {e}")
            return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='数据库结构强制同步工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 同步到最新版本（默认）
  python force_sync_database.py

  # 同步到指定版本
  python force_sync_database.py --target b2c3d4e5f6g7

  # 列出所有版本
  python force_sync_database.py --list

  # 比较版本差异
  python force_sync_database.py --compare

  # 交互式选择版本
  python force_sync_database.py --interactive

  # 生成报告
  python force_sync_database.py --report sync_report.json
        """
    )
    
    parser.add_argument('--target', '-t', type=str, help='目标版本号（默认: head）')
    parser.add_argument('--list', '-l', action='store_true', help='列出所有可用版本')
    parser.add_argument('--compare', '-c', action='store_true', help='比较当前版本和目标版本的差异')
    parser.add_argument('--interactive', '-i', action='store_true', help='交互式选择版本')
    parser.add_argument('--report', '-r', type=str, help='生成同步报告（指定输出文件）')
    parser.add_argument('--quiet', '-q', action='store_true', help='安静模式（减少输出）')
    
    args = parser.parse_args()
    
    # 获取数据库配置
    config = Config(str(project_root / "alembic.ini"))
    database_url = config.get_main_option("sqlalchemy.url")
    
    if not database_url:
        print("ERROR|未找到数据库连接配置")
        sys.exit(1)
    
    # 创建工具实例
    tool = DatabaseSyncTool(database_url, verbose=True, quiet=args.quiet)
    
    try:
        # 列出版本
        if args.list:
            tool.list_versions()
            sys.exit(0)
        
        # 比较版本
        if args.compare:
            tool.compare_versions()
            sys.exit(0)
        
        # 交互式选择
        if args.interactive:
            target_version = tool.interactive_select_version()
            if target_version is None:
                if not args.quiet:
                    print("已取消操作")
                sys.exit(0)
            success = tool.force_sync(target_version)
        else:
            # 执行同步
            success = tool.force_sync(args.target)
        
        # 生成报告
        if args.report:
            tool.generate_report(args.report)
        
        # 显示总结
        if not args.quiet:
            print("\n" + "=" * 60)
            print("同步完成")
            print("=" * 60)
            
            if success:
                print("✓ 数据库结构已完全同步")
            else:
                print("⚠ 数据库结构同步完成，但有部分问题")
                if tool.report['errors']:
                    print("\n错误:")
                    for error in tool.report['errors']:
                        print(f"  - {error}")
                if tool.report['warnings']:
                    print("\n警告:")
                    for warning in tool.report['warnings']:
                        print(f"  - {warning}")
            
            if tool.report['changes']:
                print(f"\n变更统计: {len(tool.report['changes'])} 项")
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        if not args.quiet:
            print("\n\n操作已取消")
        sys.exit(130)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

