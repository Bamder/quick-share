"""
延时机制测试

测试文件复用时的延时机制：
- 复用文件缓存时延长过期时间

使用方法:
    python scripts/test/delay_mechanism/test_delay_mechanism.py
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

def check_venv():
    in_venv = (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
        os.environ.get('VIRTUAL_ENV') is not None
    )
    if not in_venv:
        print("警告: 未检测到虚拟环境")
        # 在非交互式环境中自动继续
        if not sys.stdin.isatty():
            print("非交互式环境，自动继续...")
            return False
        try:
            if input("继续? (y/n): ").strip().lower() != 'y':
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("输入取消，退出测试")
            sys.exit(0)
    return in_venv

check_venv()

from app.utils.pickup_code import DatetimeUtil
from datetime import datetime, timedelta
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))
from test_utils import *

# 配置日志输出到控制台
logging.basicConfig(level=logging.INFO, format='%(message)s')

logger = logging.getLogger(__name__)


def test_delay_extension():
    """测试延时延长机制"""
    log_test_start("延时延长机制")

    try:
        # 导入必要的模块
        from app.services.cache_service import chunk_cache, file_info_cache
        from app.services.mapping_service import update_cache_expire_at
        from app.extensions import SessionLocal
        from app.models.user import User
        from app.models.file import File
        from app.models.pickup_code import PickupCode
        from app.utils.pickup_code import generate_unique_pickup_code

        db = SessionLocal()

        try:
            # 1. 创建测试用户和文件
            user = User(username="test_delay_user", password_hash="dummy_hash")
            db.add(user)
            db.flush()

            file_record = File(
                original_name="test_delay_file.txt",
                stored_name="stored_delay_file",
                size=1024,
                hash="delay_test_hash",
                mime_type="text/plain",
                uploader_id=user.id
            )
            db.add(file_record)
            db.flush()

            # 2. 创建初始取件码（标识码）
            original_lookup_code, _ = generate_unique_pickup_code(db)
            original_expire_at = DatetimeUtil.now() + timedelta(hours=1)

            pickup_code = PickupCode(
                code=original_lookup_code,
                file_id=file_record.id,
                status="waiting",
                used_count=0,
                limit_count=3,
                expire_at=original_expire_at,
                created_at=DatetimeUtil.now()
            )
            db.add(pickup_code)
            db.commit()

            # 3. 设置初始缓存数据
            chunks = {
                0: {
                    'data': b'test_chunk_data',
                    'hash': 'test_hash',
                    'pickup_expire_at': original_expire_at,
                    'expires_at': original_expire_at,
                }
            }
            file_info = {
                'fileName': 'test_delay_file.txt',
                'fileSize': 1024,
                'mimeType': 'text/plain',
                'totalChunks': 1,
                'uploadedAt': DatetimeUtil.now(),
                'pickup_expire_at': original_expire_at,
            }

            chunk_cache.set(original_lookup_code, chunks, user.id)
            file_info_cache.set(original_lookup_code, file_info, user.id)

            # 4. 验证初始缓存设置
            if not chunk_cache.exists(original_lookup_code, user.id):
                log_error("✗ 初始文件块缓存设置失败")
                return False

            initial_chunks = chunk_cache.get(original_lookup_code, user.id)
            initial_expire = initial_chunks[0]['expires_at']
            log_info(f"初始过期时间: {initial_expire}")

            # 5. 创建新取件码（模拟文件复用）
            new_lookup_code, _ = generate_unique_pickup_code(db)
            new_expire_at = DatetimeUtil.now() + timedelta(hours=2)  # 更晚的过期时间

            new_pickup_code = PickupCode(
                code=new_lookup_code,
                file_id=file_record.id,
                status="waiting",
                used_count=0,
                limit_count=3,
                expire_at=new_expire_at,
                created_at=DatetimeUtil.now()
            )
            db.add(new_pickup_code)
            db.commit()

            # 6. 执行延时延长（模拟复用时的缓存更新）
            update_cache_expire_at(original_lookup_code, new_expire_at, db, user.id)

            # 7. 验证缓存过期时间已被延长
            updated_chunks = chunk_cache.get(original_lookup_code, user.id)
            updated_expire = updated_chunks[0]['expires_at']

            log_info(f"更新后过期时间: {updated_expire}")

            # 检查过期时间是否被延长
            if updated_expire >= new_expire_at:
                log_info("✓ 缓存过期时间成功延长")
                success = True
            else:
                log_error(f"✗ 缓存过期时间未延长: {updated_expire} < {new_expire_at}")
                success = False

            # 8. 清理测试数据
            chunk_cache.delete(original_lookup_code, user.id)
            file_info_cache.delete(original_lookup_code, user.id)

            db.query(PickupCode).filter(PickupCode.code.in_([original_lookup_code, new_lookup_code])).delete()
            db.query(File).filter(File.id == file_record.id).delete()
            db.query(User).filter(User.id == user.id).delete()
            db.commit()

            return success

        finally:
            db.close()

    except Exception as e:
        log_error(f"延时延长测试失败: {e}")
        return False


def run_delay_mechanism_tests():
    """运行延时机制测试"""
    log_section("延时机制测试")

    tests = [
        ("延时测试", [
            test_delay_extension,
        ]),
    ]

    total_passed = 0
    total_tests = 0

    for section_name, section_tests in tests:
        log_subsection(f"{section_name} ({len(section_tests)} 个测试)")

        section_passed = 0
        for test_func in section_tests:
            try:
                if test_func():
                    section_passed += 1
                    total_passed += 1
                total_tests += 1
            except Exception as e:
                log_error(f"测试异常: {e}")
                total_tests += 1

        log_info(f"{section_name} 通过: {section_passed}/{len(section_tests)}")

    log_separator("测试结果汇总")
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    log_info(f"总测试数: {total_tests}")
    log_info(f"通过测试: {total_passed}")
    log_info(f"失败测试: {total_tests - total_passed}")
    log_info(f"成功率: {success_rate:.1f}%")
    if total_passed == total_tests:
        log_success("所有延时机制测试通过！🎉")
    else:
        log_error("部分延时机制测试失败")

    return total_passed == total_tests


if __name__ == "__main__":
    success = run_delay_mechanism_tests()
    sys.exit(0 if success else 1)
