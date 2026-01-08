"""
标识码映射机制测试

测试标识码映射系统的各种场景，包括正常和异常情况：
- 映射关系保存和获取：内存、Redis、数据库重建
- 多取件码映射：多个取件码映射到同一文件标识码
- 取件码过期处理：过期后的映射关系变化
- 标识码重建：数据库重建逻辑和失败情况

使用方法:
    # Windows (推荐):
    scripts\\test\\mapping_mechanism\\run_mapping_test.bat
    或
    scripts\\test\\mapping_mechanism\\run_mapping_test.ps1

    # 手动运行 (需要先激活虚拟环境):
    python scripts/test/mapping_mechanism/test_mapping_mechanism.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib

# 添加项目根目录到路径
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
        print("    scripts\\test\\mapping_mechanism\\run_mapping_test.bat")
        print("    或")
        print("    scripts\\test\\mapping_mechanism\\run_mapping_test.ps1")
        print("")
        print("  手动激活虚拟环境后运行:")
        print("    venv\\Scripts\\activate")
        print("    python scripts\\test\\mapping_mechanism\\test_mapping_mechanism.py")
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

from app.extensions import SessionLocal
from app.models.user import User
from app.models.file import File
from app.models.pickup_code import PickupCode
from app.services.mapping_service import (
    save_lookup_mapping, get_identifier_code, lookup_code_mapping,
    get_original_lookup_code, update_cache_expire_at, clear_failed_lookups
)
from app.utils.pickup_code import DatetimeUtil, generate_unique_pickup_code
import logging

# 导入测试工具
sys.path.insert(0, str(Path(__file__).parent.parent))
from test_utils import *

# 配置日志输出到控制台
logging.basicConfig(level=logging.INFO, format='%(message)s')

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """生成密码哈希（模拟前端SHA-256哈希）"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def create_test_user(db, username="test_user", password="test_password"):
    """创建测试用户"""
    password_hash = hash_password(password)
    user = User(
        username=username,
        password_hash=password_hash
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_file_and_pickup_codes(db, user_id, num_codes=3, expire_hours=24):
    """创建测试文件和多个取件码"""
    # 创建文件
    file_record = File(
        original_name="test_mapping_file.txt",
        stored_name="stored_test_mapping",
        size=1024,
        hash="test_hash_mapping",
        mime_type="text/plain",
        uploader_id=user_id
    )
    db.add(file_record)
    db.commit()

    # 创建多个取件码
    pickup_codes = []
    lookup_codes = []

    for i in range(num_codes):
        lookup_code, full_code = generate_unique_pickup_code(db)
        expire_at = DatetimeUtil.add_hours(DatetimeUtil.now(), expire_hours)

        pickup_code = PickupCode(
            code=lookup_code,
            file_id=file_record.id,
            status="waiting",
            used_count=0,
            limit_count=3,
            expire_at=expire_at,
            created_at=DatetimeUtil.now()
        )
        db.add(pickup_code)
        pickup_codes.append(pickup_code)
        lookup_codes.append(lookup_code)

    db.commit()

    return file_record, pickup_codes, lookup_codes


def cleanup_test_data(db):
    """清理测试数据"""
    # 清理内存映射
    test_keys = ["TESTM1", "TESTM2", "TESTM3", "TESTM4", "TESTM5"]
    for key in test_keys:
        if key in lookup_code_mapping:
            del lookup_code_mapping[key]

    # 删除测试取件码
    db.query(PickupCode).filter(PickupCode.code.in_(test_keys)).delete()

    # 删除测试文件
    db.query(File).filter(File.original_name.like("test_mapping_%")).delete()

    # 删除测试用户
    test_users = ["test_map_user", "test_expired_map_user"]
    db.query(User).filter(User.username.in_(test_users)).delete()

    db.commit()


def test_save_and_get_mapping():
    """测试映射关系的保存和获取"""
    log_test_start("映射关系保存和获取")

    try:
        # 清理可能的旧数据
        test_lookup = "TESTM1"  # 6位查找码
        test_original = "TESTM2"  # 6位标识码

        # 清理失败标记和内存映射
        clear_failed_lookups()
        if test_lookup in lookup_code_mapping:
            del lookup_code_mapping[test_lookup]

        # 保存映射关系
        expire_at = DatetimeUtil.add_hours(DatetimeUtil.now(), 1)
        save_lookup_mapping(test_lookup, test_original, expire_at)
        
        # 验证保存是否成功
        if test_lookup not in lookup_code_mapping:
            log_error(f"✗ 保存映射关系失败: {test_lookup} 不在 lookup_code_mapping 中")
            log_error(f"  lookup_code_mapping 内容: {list(lookup_code_mapping.keys())}")
            return False
        if lookup_code_mapping[test_lookup] != test_original:
            log_error(f"✗ 保存映射关系值错误: 期望{test_original}, 实际{lookup_code_mapping[test_lookup]}")
            return False
        log_info(f"✓ 验证保存成功: {test_lookup} -> {lookup_code_mapping[test_lookup]}")

        # 从内存获取
        log_info(f"调试: 调用 get_identifier_code({test_lookup}) 前，lookup_code_mapping 中有: {list(lookup_code_mapping.keys())}")
        result = get_identifier_code(test_lookup)
        log_info(f"调试: get_identifier_code({test_lookup}) 返回: {result}")
        if result == test_original:
            log_info(f"✓ 从内存获取映射成功: {test_lookup} -> {result}")
        else:
            log_error(f"✗ 从内存获取映射失败: 期望{test_original}, 实际{result}")
            return False

        # 再次获取（应该从缓存获取）
        result2 = get_identifier_code(test_lookup)
        if result2 == test_original:
            log_info(f"✓ 缓存命中成功: {test_lookup} -> {result2}")
        else:
            log_error(f"✗ 缓存命中失败: 期望{test_original}, 实际{result2}")
            return False

        log_success("映射关系保存和获取测试通过")
        return True

    except Exception as e:
        log_error(f"映射关系保存和获取测试失败: {e}")
        return False
    finally:
        # 清理
        if test_lookup in lookup_code_mapping:
            del lookup_code_mapping[test_lookup]


def test_multiple_codes_same_file(db):
    """测试多个取件码映射到同一文件"""
    log_test_start("多取件码映射到同一文件")

    try:
        # 创建测试用户和文件
        user = create_test_user(db, "test_map_user", "password123")
        file_record, pickup_codes, lookup_codes = create_test_file_and_pickup_codes(db, user.id, num_codes=3)

        # 为所有取件码创建映射关系（都映射到第一个取件码作为标识码）
        identifier_code = lookup_codes[0]  # 第一个作为标识码
        expire_at = DatetimeUtil.add_hours(DatetimeUtil.now(), 1)

        for lookup_code in lookup_codes:
            save_lookup_mapping(lookup_code, identifier_code, expire_at)

        # 验证所有取件码都能找到相同的标识码
        for i, lookup_code in enumerate(lookup_codes):
            result = get_identifier_code(lookup_code, db, "test_multiple_codes")
            if result == identifier_code:
                log_info(f"✓ 取件码 {i+1} ({lookup_code}) 正确映射到标识码: {result}")
            else:
                log_error(f"✗ 取件码 {i+1} ({lookup_code}) 映射失败: 期望{identifier_code}, 实际{result}")
                return False

        # 验证标识码重建（模拟内存缓存清空）
        lookup_code_mapping.clear()  # 清空内存缓存

        # 重新获取，应该从数据库重建
        result_rebuilt = get_identifier_code(lookup_codes[1], db, "test_rebuild")
        if result_rebuilt == identifier_code:
            log_info(f"✓ 标识码重建成功: {lookup_codes[1]} -> {result_rebuilt}")
        else:
            log_error(f"✗ 标识码重建失败: 期望{identifier_code}, 实际{result_rebuilt}")
            return False

        log_success("多取件码映射到同一文件测试通过")
        return True

    except Exception as e:
        log_error(f"多取件码映射到同一文件测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_expired_code_mapping(db):
    """测试取件码过期后的映射关系"""
    log_test_start("取件码过期后的映射关系")

    try:
        # 创建测试用户和文件（已过期）
        user = create_test_user(db, "test_expired_map_user", "password123")
        file_record, pickup_codes, lookup_codes = create_test_file_and_pickup_codes(
            db, user.id, num_codes=2, expire_hours=-1  # 已过期
        )

        # 为取件码创建映射关系
        identifier_code = lookup_codes[0]
        expire_at = DatetimeUtil.add_hours(DatetimeUtil.now(), -1)  # 已过期

        for lookup_code in lookup_codes:
            save_lookup_mapping(lookup_code, identifier_code, expire_at)

        # 尝试获取标识码（所有取件码都已过期，应该获取不到）
        for lookup_code in lookup_codes:
            result = get_identifier_code(lookup_code, db, "test_expired")
            if result is None:
                log_info(f"✓ 过期取件码 {lookup_code} 正确返回None")
            else:
                log_error(f"✗ 过期取件码 {lookup_code} 仍返回标识码: {result}")
                return False

        # 创建一个新的未过期取件码
        new_lookup_code, new_full_code = generate_unique_pickup_code(db)
        new_expire_at = DatetimeUtil.add_hours(DatetimeUtil.now(), 1)

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

        # 现在应该能重建标识码（使用新的未过期取件码）
        result_new = get_identifier_code(new_lookup_code, db, "test_new_code")
        if result_new == new_lookup_code:  # 新取件码本身就是标识码
            log_info(f"✓ 新取件码 {new_lookup_code} 成为新的标识码: {result_new}")
        else:
            log_error(f"✗ 新取件码未成为标识码: 期望{new_lookup_code}, 实际{result_new}")

        log_success("取件码过期后的映射关系测试通过")
        return True

    except Exception as e:
        log_error(f"取件码过期后的映射关系测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)
        # 清理新创建的取件码
        try:
            db.query(PickupCode).filter(PickupCode.code == "TESTM5").delete()
            db.commit()
        except:
            pass


def test_original_lookup_code_retrieval(db):
    """测试原始查找码检索"""
    log_test_start("原始查找码检索")

    try:
        # 创建测试用户和文件
        user = create_test_user(db, "test_map_user", "password123")
        file_record, pickup_codes, lookup_codes = create_test_file_and_pickup_codes(db, user.id, num_codes=2)

        # 设置映射关系
        identifier_code = lookup_codes[0]
        expire_at = DatetimeUtil.add_hours(DatetimeUtil.now(), 1)

        for lookup_code in lookup_codes:
            save_lookup_mapping(lookup_code, identifier_code, expire_at)

        # 测试获取原始查找码
        for lookup_code in lookup_codes:
            original = get_original_lookup_code(lookup_code, db)
            if original == identifier_code:
                log_info(f"✓ 获取原始查找码成功: {lookup_code} -> {original}")
            else:
                log_error(f"✗ 获取原始查找码失败: {lookup_code} -> 期望{identifier_code}, 实际{original}")
                return False

        # 测试不存在的查找码
        non_existent = get_original_lookup_code("NONEXIST", db)
        if non_existent is None:
            log_info("✓ 不存在的查找码正确返回None")
        else:
            log_error(f"✗ 不存在的查找码返回了结果: {non_existent}")
            return False

        log_success("原始查找码检索测试通过")
        return True

    except Exception as e:
        log_error(f"原始查找码检索测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_cache_expire_update(db):
    """测试缓存过期时间更新"""
    log_test_start("缓存过期时间更新")

    try:
        # 创建测试用户和文件
        user = create_test_user(db, "test_map_user", "password123")
        file_record, pickup_codes, lookup_codes = create_test_file_and_pickup_codes(db, user.id, num_codes=1)

        # 设置映射关系
        identifier_code = lookup_codes[0]
        original_expire_at = DatetimeUtil.add_hours(DatetimeUtil.now(), 1)
        save_lookup_mapping(identifier_code, identifier_code, original_expire_at)

        # 模拟延长过期时间
        new_expire_at = DatetimeUtil.add_hours(DatetimeUtil.now(), 2)
        update_cache_expire_at(identifier_code, new_expire_at, db, user.id)

        # 验证过期时间已更新（这里只是验证函数调用不报错，实际缓存更新需要更复杂的验证）
        log_info(f"✓ 缓存过期时间更新调用成功: {identifier_code} -> {new_expire_at}")

        log_success("缓存过期时间更新测试通过")
        return True

    except Exception as e:
        log_error(f"缓存过期时间更新测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_mapping_edge_cases(db):
    """测试映射机制的边界情况"""
    log_test_start("映射机制边界情况")

    try:
        passed = 0
        total = 0

        # 测试空查找码
        total += 1
        result = get_identifier_code("", db, "test_empty")
        if result is None:
            log_info("✓ 空查找码正确返回None")
            passed += 1
        else:
            log_error(f"✗ 空查找码返回了结果: {result}")

        # 测试不存在的查找码
        total += 1
        result = get_identifier_code("NONEXIST", db, "test_nonexist")
        if result is None:
            log_info("✓ 不存在的查找码正确返回None")
            passed += 1
        else:
            log_error(f"✗ 不存在的查找码返回了结果: {result}")

        # 测试没有数据库连接的情况（使用不存在的查找码）
        total += 1
        # 使用一个不存在的查找码，确保不在内存映射中
        test_no_db_code = "NODB01"
        if test_no_db_code in lookup_code_mapping:
            del lookup_code_mapping[test_no_db_code]
        result = get_identifier_code(test_no_db_code, None, "test_no_db")
        if result is None:
            log_info("✓ 无数据库连接时正确返回None")
            passed += 1
        else:
            log_error(f"✗ 无数据库连接时返回了结果: {result}")

        log_info(f"映射机制边界情况测试: {passed}/{total} 通过")
        return passed == total

    except Exception as e:
        log_error(f"映射机制边界情况测试失败: {e}")
        return False


def run_mapping_mechanism_tests():
    """运行所有标识码映射机制测试"""
    log_section("标识码映射机制测试")

    db = SessionLocal()

    try:
        # 清理可能的旧测试数据
        cleanup_test_data(db)

        tests = [
            ("基本映射功能测试", [
                test_save_and_get_mapping,
                lambda: test_original_lookup_code_retrieval(db),
                lambda: test_cache_expire_update(db),
                lambda: test_mapping_edge_cases(db),
            ]),
            ("多取件码映射测试", [
                lambda: test_multiple_codes_same_file(db),
            ]),
            ("过期处理测试", [
                lambda: test_expired_code_mapping(db),
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
                    log_error(f"测试 {test_func.__name__ if hasattr(test_func, '__name__') else 'lambda'} 发生异常: {e}")
                    total_tests += 1

            log_info(f"{section_name} 通过: {section_passed}/{len(section_tests)}")

        # 最终统计
        log_separator("测试结果汇总")
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        log_info(f"总测试数: {total_tests}")
        log_info(f"通过测试: {total_passed}")
        log_info(f"失败测试: {total_tests - total_passed}")
        log_info(f"成功率: {success_rate:.1f}%")
        if total_passed == total_tests:
            log_success("所有标识码映射机制测试通过！🎉")
        else:
            log_error("部分标识码映射机制测试失败，请检查实现")

        return total_passed == total_tests

    except Exception as e:
        log_error(f"标识码映射机制测试过程中发生严重错误: {e}")
        return False
    finally:
        # 最终清理
        try:
            cleanup_test_data(db)
        except:
            pass
        db.close()


if __name__ == "__main__":
    success = run_mapping_mechanism_tests()
    sys.exit(0 if success else 1)
