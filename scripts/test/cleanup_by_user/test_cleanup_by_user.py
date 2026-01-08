"""
测试清理服务按用户ID正确清理缓存

使用方法:
    # Windows (推荐):
    scripts\test\cleanup_by_user\run_cleanup_test.bat
    或
    scripts\test\cleanup_by_user\run_cleanup_test.ps1
    
    # 手动运行 (需要先激活虚拟环境):
    python scripts/test/cleanup_by_user/test_cleanup_by_user.py
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
# 文件位置: scripts/test/cleanup_by_user/test_cleanup_by_user.py
# 需要向上3层到达项目根目录
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 检查是否在虚拟环境中
def check_venv():
    """检查是否在虚拟环境中运行"""
    in_venv = (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
        os.environ.get('VIRTUAL_ENV') is not None
    )
    
    if not in_venv:
        print("=" * 60)
        print("警告: 未检测到虚拟环境")
        print("=" * 60)
        print("建议使用以下方式运行测试:")
        print("  Windows:")
        print("    scripts\\test\\run_cleanup_test.bat")
        print("    或")
        print("    scripts\\test\\run_cleanup_test.ps1")
        print("")
        print("  手动激活虚拟环境后运行:")
        print("    venv\\Scripts\\activate")
        print("    python scripts\\test\\test_cleanup_by_user.py")
        print("=" * 60)
        print("")
        
        # 询问是否继续
        try:
            response = input("是否继续运行? (y/n): ").strip().lower()
            if response != 'y':
                print("已取消")
                sys.exit(0)
        except (KeyboardInterrupt, EOFError):
            print("\n已取消")
            sys.exit(0)
    
    return in_venv

# 在导入其他模块前检查虚拟环境
check_venv()

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.extensions import SessionLocal
from app.services.cleanup_service import cleanup_expired_chunks
from app.services.cache_service import chunk_cache, file_info_cache, encrypted_key_cache
from app.models.file import File
from app.models.pickup_code import PickupCode
from app.models.user import User
from app.utils.pickup_code import ensure_aware_datetime
import logging

# 导入测试工具
sys.path.insert(0, str(Path(__file__).parent.parent))
from test_utils import *

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def create_test_data(db: Session):
    """创建测试数据：两个用户，每个用户有已过期和未过期的数据"""
    
    # 先清理可能存在的旧测试数据
    db.query(PickupCode).filter(PickupCode.code.in_(["TEST01", "TEST02", "TEST03", "TEST04"])).delete()
    db.query(File).filter(File.original_name.like("test_file_TEST%")).delete()
    db.query(User).filter(User.username.in_(["test_user_1", "test_user_2"])).delete()
    db.commit()
    
    # 创建测试用户
    user1 = User(
        username="test_user_1",
        password_hash="dummy_hash_for_test"  # 测试用的假哈希
    )
    db.add(user1)
    db.flush()
    
    user2 = User(
        username="test_user_2",
        password_hash="dummy_hash_for_test"  # 测试用的假哈希
    )
    db.add(user2)
    db.flush()
    
    logger.info(f"创建测试用户: user1_id={user1.id}, user2_id={user2.id}")
    
    now = datetime.now(timezone.utc)
    
    # 用户1的数据：已过期（设置为1分钟前过期，这样缓存管理器会接受）
    lookup_code_1_expired = "TEST01"
    expire_at_1 = now - timedelta(minutes=1)  # 1分钟前过期
    
    # 用户1的数据：未过期
    lookup_code_1_valid = "TEST02"
    expire_at_2 = now + timedelta(hours=1)  # 1小时后过期
    
    # 用户2的数据：已过期
    lookup_code_2_expired = "TEST03"
    expire_at_3 = now - timedelta(minutes=1)  # 1分钟前过期
    
    # 用户2的数据：未过期
    lookup_code_2_valid = "TEST04"
    expire_at_4 = now + timedelta(hours=1)  # 1小时后过期
    
    logger.info(f"测试数据配置:")
    logger.info(f"  用户1 - 已过期: {lookup_code_1_expired} (过期时间: {expire_at_1})")
    logger.info(f"  用户1 - 未过期: {lookup_code_1_valid} (过期时间: {expire_at_2})")
    logger.info(f"  用户2 - 已过期: {lookup_code_2_expired} (过期时间: {expire_at_3})")
    logger.info(f"  用户2 - 未过期: {lookup_code_2_valid} (过期时间: {expire_at_4})")
    
    # 创建文件记录
    files = []
    for i, (lookup_code, user_id, expire_at) in enumerate([
        (lookup_code_1_expired, user1.id, expire_at_1),
        (lookup_code_1_valid, user1.id, expire_at_2),
        (lookup_code_2_expired, user2.id, expire_at_3),
        (lookup_code_2_valid, user2.id, expire_at_4),
    ]):
        file_record = File(
            original_name=f"test_file_{lookup_code}.txt",
            stored_name=f"stored_{lookup_code}",
            size=1000,
            hash=f"hash_{lookup_code}",
            mime_type="text/plain",
            uploader_id=user_id,
            created_at=now
        )
        db.add(file_record)
        db.flush()
        files.append((lookup_code, file_record.id, user_id, expire_at))
    
    # 创建取件码记录
    pickup_codes = []
    for lookup_code, file_id, user_id, expire_at in files:
        pickup_code = PickupCode(
            code=lookup_code,
            file_id=file_id,
            status="waiting",
            used_count=0,
            limit_count=3,
            expire_at=expire_at,
            created_at=now
        )
        db.add(pickup_code)
        pickup_codes.append((lookup_code, user_id))
    
    db.commit()
    logger.info(f"创建了 {len(files)} 个文件记录和 {len(pickup_codes)} 个取件码记录")
    
    return pickup_codes


def setup_test_cache(pickup_codes, db: Session):
    """设置测试缓存数据"""
    now = datetime.now(timezone.utc)
    
    # 从数据库获取过期时间和用户ID映射
    lookup_to_user = {code: uid for code, uid in pickup_codes}
    
    # 从数据库获取过期时间
    for lookup_code, user_id in pickup_codes:
        pickup_code_obj = db.query(PickupCode).filter(PickupCode.code == lookup_code).first()
        if not pickup_code_obj:
            logger.warning(f"找不到取件码: {lookup_code}")
            continue
        
        expire_at = ensure_aware_datetime(pickup_code_obj.expire_at)
        is_expired = now > expire_at
        
        # 对于已过期的数据，我们需要使用一个未来的过期时间先存储，确保能被存储
        # 清理服务基于数据库中的取件码过期状态，而不是 Redis TTL
        # 所以我们可以用一个较长的 TTL 存储，但数据中的 pickup_expire_at 设置为已过期
        if is_expired:
            # 已过期的数据：先用一个足够长的时间（比如30秒）存储，确保能被存储
            # 清理服务会基于数据库中的取件码状态来清理，而不是 Redis TTL
            from app.utils.cache import cache_manager
            from app.services.cache_service import _make_cache_key
            
            # 使用底层缓存管理器直接设置
            cache_key = _make_cache_key(user_id, lookup_code)
            
            # 使用一个足够长的时间（30秒）存储，确保能被存储
            # 清理服务会基于数据库中的取件码过期状态来清理，而不是 Redis TTL
            temp_expire_at = now + timedelta(seconds=30)
            
            # 设置文件块缓存（数据中的 pickup_expire_at 是已过期的）
            chunks = {
                0: {
                    'data': b'test_chunk_data',
                    'hash': 'test_hash',
                    'pickup_expire_at': expire_at,  # 已过期的时间
                    'expires_at': expire_at,  # 已过期的时间
                }
            }
            success1 = cache_manager.set('chunk', cache_key, chunks, temp_expire_at)
            
            # 设置文件信息缓存
            file_info = {
                'fileName': f'test_file_{lookup_code}.txt',
                'fileSize': 1000,
                'mimeType': 'text/plain',
                'totalChunks': 1,
                'uploadedAt': now,
                'pickup_expire_at': expire_at,  # 已过期的时间
            }
            success2 = cache_manager.set('file_info', cache_key, file_info, temp_expire_at)
            
            # 设置加密密钥缓存
            success3 = cache_manager.set('encrypted_key', cache_key, f'encrypted_key_{lookup_code}', temp_expire_at)
            
            # 检查是否成功存储
            if not (success1 and success2 and success3):
                logger.warning(f"部分缓存设置失败: lookup_code={lookup_code}, chunk={success1}, file_info={success2}, key={success3}")
            else:
                logger.info(f"已过期数据缓存设置成功: lookup_code={lookup_code}, Redis TTL=30秒, pickup_expire_at={expire_at}（已过期）")
        else:
            # 未过期的数据：正常设置
            chunks = {
                0: {
                    'data': b'test_chunk_data',
                    'hash': 'test_hash',
                    'pickup_expire_at': expire_at,
                    'expires_at': expire_at,
                }
            }
            chunk_cache.set(lookup_code, chunks, user_id)
            
            file_info = {
                'fileName': f'test_file_{lookup_code}.txt',
                'fileSize': 1000,
                'mimeType': 'text/plain',
                'totalChunks': 1,
                'uploadedAt': now,
                'pickup_expire_at': expire_at,
            }
            file_info_cache.set(lookup_code, file_info, user_id)
            
            encrypted_key_cache.set(lookup_code, f'encrypted_key_{lookup_code}', user_id, expire_at)
        
        logger.info(f"设置缓存: lookup_code={lookup_code}, user_id={user_id}, "
                   f"过期时间={expire_at}, 是否过期={is_expired}")
    
    logger.info("测试缓存数据已设置")


def verify_cache_state(expected_state, test_name):
    """验证缓存状态"""
    log_separator(f"验证测试: {test_name}")
    
    passed = 0
    total = len(expected_state)
    
    for lookup_code, user_id, should_exist in expected_state:
        chunk_exists = chunk_cache.exists(lookup_code, user_id)
        file_info_exists = file_info_cache.exists(lookup_code, user_id)
        key_exists = encrypted_key_cache.exists(lookup_code, user_id)
        
        all_match = (chunk_exists == should_exist and 
                    file_info_exists == should_exist and 
                    key_exists == should_exist)
        
        if all_match:
            passed += 1
            log_success(f"lookup_code={lookup_code}, user_id={user_id}, 应该存在={should_exist}, "
                       f"实际: chunk={chunk_exists}, file_info={file_info_exists}, key={key_exists}")
        else:
            log_error(f"lookup_code={lookup_code}, user_id={user_id}, 应该存在={should_exist}, "
                     f"实际: chunk={chunk_exists}, file_info={file_info_exists}, key={key_exists}")
    
    success_rate = (passed / total * 100) if total > 0 else 0
    log_info(f"{test_name}: {passed}/{total} 通过 ({success_rate:.1f}%)")
    
    return passed == total


def test_cleanup_by_user():
    """测试清理服务按用户ID正确清理"""
    log_section("清理服务按用户ID清理测试")
    
    db: Session = SessionLocal()
    
    try:
        
        # 1. 创建测试数据
        logger.info("\n步骤1: 创建测试数据")
        pickup_codes = create_test_data(db)
        
        # 2. 设置测试缓存
        logger.info("\n步骤2: 设置测试缓存")
        setup_test_cache(pickup_codes, db)
        
        # 3. 验证初始状态（所有数据都应该存在）
        logger.info("\n步骤3: 验证初始状态")
        # 获取实际创建的用户ID
        user1_id = None
        user2_id = None
        for lookup_code, user_id in pickup_codes:
            if lookup_code in ["TEST01", "TEST02"]:
                if user1_id is None:
                    user1_id = user_id
            elif lookup_code in ["TEST03", "TEST04"]:
                if user2_id is None:
                    user2_id = user_id
        
        logger.info(f"实际用户ID: user1_id={user1_id}, user2_id={user2_id}")
        
        expected_before = [
            ("TEST01", user1_id, True),  # 用户1，已过期，但清理前应该存在
            ("TEST02", user1_id, True),  # 用户1，未过期
            ("TEST03", user2_id, True),  # 用户2，已过期，但清理前应该存在
            ("TEST04", user2_id, True),  # 用户2，未过期
        ]
        verify_cache_state(expected_before, "清理前状态")
        
        # 4. 执行清理
        logger.info("\n步骤4: 执行清理服务")
        cleanup_expired_chunks(db)
        
        # 5. 验证清理后状态（只有未过期的数据应该存在）
        logger.info("\n步骤5: 验证清理后状态")
        expected_after = [
            ("TEST01", user1_id, False),  # 用户1，已过期，应该被清理
            ("TEST02", user1_id, True),   # 用户1，未过期，应该保留
            ("TEST03", user2_id, False),  # 用户2，已过期，应该被清理
            ("TEST04", user2_id, True),   # 用户2，未过期，应该保留
        ]
        result = verify_cache_state(expected_after, "清理后状态")
        
        # 6. 验证用户隔离（用户1的数据不应该影响用户2）
        log_info("\n步骤6: 验证用户隔离")
        # 检查用户1的缓存键
        user1_chunks = chunk_cache.keys(user_id=user1_id)
        user2_chunks = chunk_cache.keys(user_id=user2_id)
        
        log_info(f"用户1 (ID={user1_id}) 的缓存键: {user1_chunks}")
        log_info(f"用户2 (ID={user2_id}) 的缓存键: {user2_chunks}")
        
        isolation_passed = 0
        isolation_total = 2
        
        # 用户1应该只有 TEST02
        if "TEST02" in user1_chunks and "TEST01" not in user1_chunks:
            log_success("用户1的缓存隔离正确")
            isolation_passed += 1
        else:
            log_error("用户1的缓存隔离失败")
            result = False
        
        # 用户2应该只有 TEST04
        if "TEST04" in user2_chunks and "TEST03" not in user2_chunks:
            log_success("用户2的缓存隔离正确")
            isolation_passed += 1
        else:
            log_error("用户2的缓存隔离失败")
            result = False
        
        isolation_rate = (isolation_passed / isolation_total * 100) if isolation_total > 0 else 0
        log_info(f"用户隔离验证: {isolation_passed}/{isolation_total} 通过 ({isolation_rate:.1f}%)")
        
        # 7. 清理测试数据
        logger.info("\n步骤7: 清理测试数据")
        # 删除测试取件码
        for lookup_code, _ in pickup_codes:
            db.query(PickupCode).filter(PickupCode.code == lookup_code).delete()
        
        # 删除测试文件
        for lookup_code, _ in pickup_codes:
            file_record = db.query(File).filter(File.original_name.like(f"test_file_{lookup_code}%")).first()
            if file_record:
                db.delete(file_record)
        
        # 删除测试用户
        db.query(User).filter(User.username.in_(["test_user_1", "test_user_2"])).delete()
        db.commit()
        
        # 清理测试缓存
        for lookup_code, user_id in pickup_codes:
            chunk_cache.delete(lookup_code, user_id)
            file_info_cache.delete(lookup_code, user_id)
            encrypted_key_cache.delete(lookup_code, user_id)
        
        logger.info("测试数据已清理")
        
        # 8. 总结
        log_separator("测试结果")
        if result:
            log_success("所有测试通过！清理服务按用户ID正确工作")
        else:
            log_error("测试失败！请检查清理服务的实现")
        
        return result
        
    except Exception as e:
        log_error(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        try:
            db.rollback()
        except:
            pass
        db.close()


def run_cleanup_by_user_tests():
    """运行清理服务按用户ID清理测试"""
    try:
        success = test_cleanup_by_user()
        
        log_separator("测试结果汇总")
        if success:
            log_success("所有清理服务按用户ID清理测试通过！🎉")
            log_info("成功率: 100.0%")
        else:
            log_error("部分清理服务按用户ID清理测试失败，请检查实现")
            log_info("成功率: 0.0%")
        
        return success
    except Exception as e:
        log_error(f"测试执行过程中发生严重错误: {e}")
        import traceback
        traceback.print_exc()
        log_info("成功率: 0.0%")
        return False


if __name__ == "__main__":
    success = run_cleanup_by_user_tests()
    sys.exit(0 if success else 1)

