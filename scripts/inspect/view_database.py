"""
查看数据库内容脚本

功能：
- 查看文件记录（files 表）
- 查看取件码记录（pickup_codes 表）
- 显示文件与取件码的关联关系
- 显示取件码的过期状态

使用方法：
1. 直接运行：python scripts/inspect/view_database.py
2. 或使用批处理：scripts/inspect/view_database.bat
"""

import sys
import os

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import datetime, timezone
from app.extensions import SessionLocal
from app.models.file import File
from app.models.pickup_code import PickupCode
from app.utils.pickup_code import check_and_update_expired_pickup_code, ensure_aware_datetime
from app.services.mapping_service import get_identifier_code
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_datetime(dt):
    """格式化日期时间"""
    if dt is None:
        return "N/A"
    if isinstance(dt, str):
        return dt
    dt = ensure_aware_datetime(dt)
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def show_files(db):
    """显示文件记录"""
    print("\n" + "=" * 80)
    print("文件记录 (files 表) - 仅元数据")
    print("=" * 80)
    print("  注意：此表只存储文件元数据（文件名、大小、哈希等）")
    print("  文件实际数据（加密后的文件块）存储在缓存中（Redis/内存），不在数据库中")
    print()
    
    try:
        files = db.query(File).order_by(File.created_at.desc()).all()
        if not files:
            print("  无文件记录")
            return
        
        print(f"  总文件数: {len(files)}")
        print()
        
        for file in files[:20]:  # 只显示前20个
            print(f"  文件ID: {file.id}")
            print(f"    原始名称: {file.original_name}")
            print(f"    存储名称: {file.stored_name}")
            print(f"    文件大小: {format_size(file.size)}")
            print(f"    哈希: {file.hash[:32] + '...' if file.hash and len(file.hash) > 32 else file.hash or 'N/A'}")
            print(f"    MIME类型: {file.mime_type or 'N/A'}")
            print(f"    上传者ID: {file.uploader_id or '匿名'}")
            print(f"    创建时间: {format_datetime(file.created_at)}")
            print(f"    更新时间: {format_datetime(file.updated_at)}")
            
            # 查询关联的取件码数量
            pickup_code_count = db.query(PickupCode).filter(PickupCode.file_id == file.id).count()
            print(f"    关联取件码数: {pickup_code_count}")
            print()
        
        if len(files) > 20:
            print(f"  ... 还有 {len(files) - 20} 个文件记录未显示")
    except Exception as e:
        print(f"  获取文件记录失败: {e}")


def show_pickup_codes(db):
    """显示取件码记录"""
    print("\n" + "=" * 80)
    print("取件码记录 (pickup_codes 表)")
    print("=" * 80)
    
    try:
        pickup_codes = db.query(PickupCode).order_by(PickupCode.created_at.desc()).all()
        if not pickup_codes:
            print("  无取件码记录")
            return
        
        print(f"  总取件码数: {len(pickup_codes)}")
        print()
        
        now = datetime.now(timezone.utc)
        expired_count = 0
        active_count = 0
        
        for pickup_code in pickup_codes[:30]:  # 只显示前30个
            # 检查并更新过期状态
            check_and_update_expired_pickup_code(pickup_code, db)
            db.refresh(pickup_code)
            
            expire_at = ensure_aware_datetime(pickup_code.expire_at) if pickup_code.expire_at else None
            is_expired = pickup_code.status == "expired" or (expire_at and expire_at <= now)
            
            if is_expired:
                expired_count += 1
            else:
                active_count += 1
            
            print(f"  取件码: {pickup_code.code}")
            print(f"    文件ID: {pickup_code.file_id}")
            print(f"    状态: {pickup_code.status}")
            print(f"    使用次数: {pickup_code.used_count}/{pickup_code.limit_count}")
            print(f"    过期时间: {format_datetime(pickup_code.expire_at)}")
            if expire_at:
                if expire_at <= now:
                    print(f"    过期状态: 已过期")
                else:
                    remaining = expire_at - now
                    hours = remaining.total_seconds() / 3600
                    print(f"    过期状态: 未过期 (剩余 {hours:.1f} 小时)")
            print(f"    上传者IP: {pickup_code.uploader_ip or 'N/A'}")
            print(f"    创建时间: {format_datetime(pickup_code.created_at)}")
            print(f"    更新时间: {format_datetime(pickup_code.updated_at)}")
            
            # 获取标识码
            try:
                identifier_code = get_identifier_code(pickup_code.code, db)
                if identifier_code and identifier_code != pickup_code.code:
                    print(f"    标识码: {identifier_code} (映射)")
                else:
                    print(f"    标识码: {pickup_code.code} (自映射)")
            except Exception as e:
                print(f"    标识码: 获取失败 ({e})")
            
            print()
        
        if len(pickup_codes) > 30:
            print(f"  ... 还有 {len(pickup_codes) - 30} 个取件码记录未显示")
        
        print(f"\n  统计:")
        print(f"    活跃取件码: {active_count}")
        print(f"    已过期取件码: {expired_count}")
    except Exception as e:
        print(f"  获取取件码记录失败: {e}")


def show_file_pickup_relations(db):
    """显示文件与取件码的关联关系"""
    print("\n" + "=" * 80)
    print("文件与取件码关联关系")
    print("=" * 80)
    print("  注意：如果关联取件码数为0，可能是：")
    print("    1. 取件码已过期并被清理")
    print("    2. 取件码已被手动删除")
    print("    3. 文件记录是测试数据或孤立记录")
    print()
    
    try:
        files = db.query(File).order_by(File.created_at.desc()).limit(10).all()
        if not files:
            print("  无文件记录")
            return
        
        files_with_codes = 0
        files_without_codes = 0
        
        for file in files:
            pickup_codes = db.query(PickupCode).filter(
                PickupCode.file_id == file.id
            ).order_by(PickupCode.created_at.asc()).all()
            
            print(f"\n  文件: {file.original_name} (ID: {file.id})")
            print(f"    大小: {format_size(file.size)}")
            print(f"    关联取件码数: {len(pickup_codes)}")
            
            if len(pickup_codes) > 0:
                files_with_codes += 1
                # 获取标识码
                first_code = pickup_codes[0].code
                try:
                    identifier_code = get_identifier_code(first_code, db)
                    print(f"    标识码: {identifier_code}")
                except Exception as e:
                    print(f"    标识码: 获取失败 ({e})")
                
                print(f"    取件码列表:")
                for pc in pickup_codes:
                    status_icon = "✓" if pc.status in ["waiting", "transferring"] else "✗"
                    print(f"      {status_icon} {pc.code} ({pc.status})")
            else:
                files_without_codes += 1
                print(f"    ⚠️  无关联取件码（可能是孤立记录或已清理）")
        
        print(f"\n  统计:")
        print(f"    有取件码的文件: {files_with_codes}")
        print(f"    无取件码的文件: {files_without_codes}")
    except Exception as e:
        print(f"  获取关联关系失败: {e}")


def show_statistics(db):
    """显示统计信息"""
    print("\n" + "=" * 80)
    print("统计信息")
    print("=" * 80)
    print("  注意：文件大小是元数据中的大小，实际文件数据存储在缓存中")
    print()
    
    try:
        # 文件统计
        total_files = db.query(File).count()
        total_size = db.query(File).with_entities(
            db.func.sum(File.size)
        ).scalar() or 0
        
        # 统计有取件码和无取件码的文件
        files_with_codes = db.query(File).join(PickupCode).distinct().count()
        files_without_codes = total_files - files_with_codes
        
        print(f"  文件统计（元数据）:")
        print(f"    总文件数: {total_files}")
        print(f"    总文件大小（元数据）: {format_size(total_size)}")
        if total_files > 0:
            print(f"    平均文件大小: {format_size(total_size / total_files)}")
        print(f"    有取件码的文件: {files_with_codes}")
        print(f"    无取件码的文件: {files_without_codes} (可能是孤立记录)")
        
        # 取件码统计
        now = datetime.now(timezone.utc)
        total_pickup_codes = db.query(PickupCode).count()
        active_pickup_codes = db.query(PickupCode).filter(
            PickupCode.status.in_(["waiting", "transferring"]),
            PickupCode.expire_at > now
        ).count()
        expired_pickup_codes = db.query(PickupCode).filter(
            PickupCode.status == "expired"
        ).count()
        
        print(f"\n  取件码统计:")
        print(f"    总取件码数: {total_pickup_codes}")
        print(f"    活跃取件码: {active_pickup_codes}")
        print(f"    已过期取件码: {expired_pickup_codes}")
        print(f"    已完成取件码: {db.query(PickupCode).filter(PickupCode.status == 'completed').count()}")
    except Exception as e:
        print(f"  获取统计信息失败: {e}")


def main():
    """主函数"""
    print("=" * 80)
    print("数据库内容查看工具")
    print("=" * 80)
    print(f"查看时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    db = SessionLocal()
    try:
        # 显示统计信息
        show_statistics(db)
        
        # 显示各种数据
        show_files(db)
        show_pickup_codes(db)
        show_file_pickup_relations(db)
        
        print("\n" + "=" * 80)
        print("查看完成")
        print("=" * 80)
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

