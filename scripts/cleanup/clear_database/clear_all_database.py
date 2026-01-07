"""
清理数据库所有内容脚本

⚠️ 警告：此脚本会删除数据库中的所有数据，请谨慎使用！

功能：
- 删除所有举报记录（reports）
- 删除所有取件码记录（pickup_codes）
- 删除所有文件记录（files）
- 可选：删除所有用户记录（users）

使用场景：
- 测试环境重置
- 开发调试
- 清理测试数据

使用方法：
1. 直接运行：python scripts/cleanup/clear_database/clear_all_database.py
2. 或使用批处理：scripts/cleanup/clear_database/clear_all_database.bat
"""

import sys
import os

# 添加项目根目录到 Python 路径
# 脚本位置: scripts/cleanup/clear_database/clear_all_database.py
# 需要向上3层到达项目根目录
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))

print(f"脚本目录: {script_dir}")
print(f"计算出的项目根目录: {project_root}")

# 验证项目根目录是否正确
if not os.path.exists(os.path.join(project_root, 'app')):
    print(f"错误: 项目根目录不正确，未找到 app 目录: {project_root}")
    sys.exit(1)

if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"已添加到 Python 路径: {project_root}")

from datetime import datetime, timezone
from app.extensions import SessionLocal
from app.models.report import Report
from app.models.pickup_code import PickupCode
from app.models.file import File
from app.models.user import User
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def show_database_stats(db):
    """显示数据库统计信息"""
    print("\n" + "=" * 80)
    print("数据库统计信息（删除前）")
    print("=" * 80)
    
    try:
        report_count = db.query(Report).count()
        pickup_code_count = db.query(PickupCode).count()
        file_count = db.query(File).count()
        user_count = db.query(User).count()
        
        print(f"  举报记录数: {report_count}")
        print(f"  取件码记录数: {pickup_code_count}")
        print(f"  文件记录数: {file_count}")
        print(f"  用户记录数: {user_count}")
    except Exception as e:
        print(f"  获取统计信息失败: {e}")


def clear_all_database(db, clear_users=False):
    """
    清理数据库所有内容
    
    参数:
    - db: 数据库会话
    - clear_users: 是否也删除用户记录（默认 False，保留用户）
    """
    print("\n" + "=" * 80)
    print("开始清理数据库...")
    print("=" * 80)
    
    deleted_counts = {
        'reports': 0,
        'pickup_codes': 0,
        'files': 0,
        'users': 0
    }
    
    try:
        # 1. 删除举报记录（reports）
        # 注意：reports 依赖 pickup_codes，但外键是 CASCADE，所以先删除也可以
        # 为了安全，还是先删除 reports
        print("\n步骤 1: 删除举报记录...")
        reports = db.query(Report).all()
        for report in reports:
            db.delete(report)
        deleted_counts['reports'] = len(reports)
        print(f"  ✓ 已删除 {deleted_counts['reports']} 条举报记录")
        
        # 2. 删除取件码记录（pickup_codes）
        # 注意：pickup_codes 依赖 files，但外键是 CASCADE，所以先删除也可以
        # 为了安全，还是先删除 pickup_codes
        print("\n步骤 2: 删除取件码记录...")
        pickup_codes = db.query(PickupCode).all()
        for pickup_code in pickup_codes:
            db.delete(pickup_code)
        deleted_counts['pickup_codes'] = len(pickup_codes)
        print(f"  ✓ 已删除 {deleted_counts['pickup_codes']} 条取件码记录")
        
        # 3. 删除文件记录（files）
        # 注意：files.uploader_id 依赖 users，但外键是 SET NULL，所以可以删除
        print("\n步骤 3: 删除文件记录...")
        files = db.query(File).all()
        for file in files:
            db.delete(file)
        deleted_counts['files'] = len(files)
        print(f"  ✓ 已删除 {deleted_counts['files']} 条文件记录")
        
        # 4. 可选：删除用户记录（users）
        if clear_users:
            print("\n步骤 4: 删除用户记录...")
            users = db.query(User).all()
            for user in users:
                db.delete(user)
            deleted_counts['users'] = len(users)
            print(f"  ✓ 已删除 {deleted_counts['users']} 条用户记录")
        else:
            print("\n步骤 4: 跳过用户记录（保留用户）")
        
        # 提交事务
        db.commit()
        print("\n" + "=" * 80)
        print("数据库清理完成")
        print("=" * 80)
        print(f"  删除统计:")
        print(f"    举报记录: {deleted_counts['reports']}")
        print(f"    取件码记录: {deleted_counts['pickup_codes']}")
        print(f"    文件记录: {deleted_counts['files']}")
        if clear_users:
            print(f"    用户记录: {deleted_counts['users']}")
        else:
            print(f"    用户记录: 保留（未删除）")
        
        return deleted_counts
        
    except Exception as e:
        db.rollback()
        logger.error(f"清理数据库失败: {e}", exc_info=True)
        raise


def main():
    """主函数"""
    print("=" * 80)
    print("⚠️  清理数据库所有内容")
    print("=" * 80)
    print()
    print("警告：此操作将删除数据库中的所有数据！")
    print("包括：")
    print("  • 所有举报记录")
    print("  • 所有取件码记录")
    print("  • 所有文件记录")
    print("  • 可选：所有用户记录（默认保留）")
    print()
    print("此操作不可逆！")
    print()
    
    # 确认操作
    confirm = input("请输入 'YES' 确认删除所有数据: ")
    if confirm != "YES":
        print("操作已取消")
        return
    
    # 询问是否删除用户
    clear_users_input = input("是否也删除用户记录？(y/N): ").strip().lower()
    clear_users = clear_users_input in ['y', 'yes']
    
    db = SessionLocal()
    try:
        # 显示删除前的统计信息
        show_database_stats(db)
        
        # 执行清理
        deleted_counts = clear_all_database(db, clear_users=clear_users)
        
        # 显示删除后的统计信息
        print("\n" + "=" * 80)
        print("数据库统计信息（删除后）")
        print("=" * 80)
        try:
            report_count = db.query(Report).count()
            pickup_code_count = db.query(PickupCode).count()
            file_count = db.query(File).count()
            user_count = db.query(User).count()
            
            print(f"  举报记录数: {report_count}")
            print(f"  取件码记录数: {pickup_code_count}")
            print(f"  文件记录数: {file_count}")
            print(f"  用户记录数: {user_count}")
        except Exception as e:
            print(f"  获取统计信息失败: {e}")
        
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        print(f"\n执行失败: {e}")

