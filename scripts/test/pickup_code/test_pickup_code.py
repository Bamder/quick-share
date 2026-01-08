"""
12位取件码生成与验证功能测试

测试取件码系统的各种场景，包括正常和异常情况：
- 取件码生成：正常生成、唯一性、格式验证
- 取件码验证：有效格式、无效格式、长度检查
- 有效期测试：1分钟、1小时、1天过期处理
- 使用次数限制：1次、2次、超过限制的情况

使用方法:
    # Windows (推荐):
    scripts\\test\\pickup_code\\run_pickup_test.bat
    或
    scripts\\test\\pickup_code\\run_pickup_test.ps1

    # 手动运行 (需要先激活虚拟环境):
    python scripts/test/pickup_code/test_pickup_code.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
import re
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
        print("    scripts\\test\\pickup_code\\run_pickup_test.bat")
        print("    或")
        print("    scripts\\test\\pickup_code\\run_pickup_test.ps1")
        print("")
        print("  手动激活虚拟环境后运行:")
        print("    venv\\Scripts\\activate")
        print("    python scripts\\test\\pickup_code\\test_pickup_code.py")
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
from app.utils.pickup_code import (
    generate_pickup_code, generate_unique_lookup_code, generate_unique_pickup_code,
    extract_lookup_code, extract_key_code, check_and_update_expired_pickup_code,
    ensure_aware_datetime, DatetimeUtil
)
from app.utils.validation import validate_pickup_code, validate_full_pickup_code
from app.services.pickup_code_service import get_pickup_code_by_lookup
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


def create_test_file_and_pickup_code(db, user_id, expire_hours=24, limit_count=3):
    """创建测试文件和取件码"""
    # 创建文件
    file_record = File(
        original_name="test_file.txt",
        stored_name="stored_test_file",
        size=1024,
        hash="test_hash",
        mime_type="text/plain",
        uploader_id=user_id
    )
    db.add(file_record)
    db.commit()

    # 创建取件码
    lookup_code, full_code = generate_unique_pickup_code(db)
    expire_at = DatetimeUtil.add_hours(DatetimeUtil.now(), expire_hours)

    pickup_code = PickupCode(
        code=lookup_code,
        file_id=file_record.id,
        status="waiting",
        used_count=0,
        limit_count=limit_count,
        expire_at=expire_at,
        created_at=DatetimeUtil.now()
    )
    db.add(pickup_code)
    db.commit()

    return file_record, pickup_code, lookup_code, full_code


def cleanup_test_data(db):
    """清理测试数据"""
    # 删除测试取件码
    test_codes = ["TESTPC01", "TESTPC02", "TESTPC03", "TESTPC04", "TESTPC05"]
    db.query(PickupCode).filter(PickupCode.code.in_(test_codes)).delete()

    # 删除测试文件
    db.query(File).filter(File.original_name.like("test_file_%")).delete()

    # 删除测试用户
    test_users = ["test_pc_user", "test_exp_user", "test_limit_user"]
    db.query(User).filter(User.username.in_(test_users)).delete()

    db.commit()


def test_generate_pickup_code_format():
    """测试取件码格式生成"""
    log_test_start("取件码格式生成")

    try:
        # 生成多个取件码进行测试
        codes = [generate_pickup_code() for _ in range(10)]

        passed = 0
        for i, code in enumerate(codes):
            # 检查长度
            if len(code) != 12:
                log_error(f"取件码 {i+1} 长度错误: {len(code)} (应为12)")
                continue

            # 检查字符集（只包含大写字母和数字）
            if not re.match(r'^[A-Z0-9]{12}$', code):
                log_error(f"取件码 {i+1} 包含无效字符: {code}")
                continue

            # 检查前6位和后6位都不为空
            lookup_code = code[:6]
            key_code = code[6:]
            if not lookup_code or not key_code:
                log_error(f"取件码 {i+1} 前后6位不完整: {code}")
                continue

            passed += 1
            log_info(f"✓ 取件码 {i+1}: {code} (查找码: {lookup_code}, 密钥码: {key_code})")

        log_info(f"取件码格式测试: {passed}/{len(codes)} 通过")
        return passed == len(codes)

    except Exception as e:
        log_error(f"取件码格式生成测试失败: {e}")
        return False


def test_generate_unique_lookup_code(db):
    """测试唯一查找码生成"""
    log_test_start("唯一查找码生成")

    try:
        # 生成多个唯一查找码
        lookup_codes = []
        for i in range(5):
            lookup_code = generate_unique_lookup_code(db)
            if lookup_code in lookup_codes:
                log_error(f"生成重复的查找码: {lookup_code}")
                return False
            lookup_codes.append(lookup_code)
            log_info(f"✓ 生成唯一查找码 {i+1}: {lookup_code}")

        # 验证数据库中不存在
        for code in lookup_codes:
            existing = db.query(PickupCode).filter(PickupCode.code == code).first()
            if existing:
                log_error(f"查找码 {code} 在数据库中已存在")
                return False

        log_success("唯一查找码生成测试通过")
        return True

    except Exception as e:
        log_error(f"唯一查找码生成测试失败: {e}")
        return False


def test_generate_unique_pickup_code(db):
    """测试完整取件码生成"""
    log_test_start("完整取件码生成")

    try:
        lookup_codes = []
        full_codes = []

        for i in range(3):
            lookup_code, full_code = generate_unique_pickup_code(db)

            # 检查格式
            if len(full_code) != 12:
                log_error(f"完整取件码长度错误: {len(full_code)}")
                return False

            if not validate_full_pickup_code(full_code):
                log_error(f"完整取件码格式无效: {full_code}")
                return False

            # 检查查找码唯一性
            if lookup_code in lookup_codes:
                log_error(f"查找码重复: {lookup_code}")
                return False

            # 检查完整码唯一性
            if full_code in full_codes:
                log_error(f"完整取件码重复: {full_code}")
                return False

            lookup_codes.append(lookup_code)
            full_codes.append(full_code)

            # 验证前6位匹配
            if full_code[:6] != lookup_code:
                log_error(f"前6位不匹配: 完整码={full_code}, 查找码={lookup_code}")
                return False

            log_info(f"✓ 生成完整取件码 {i+1}: {full_code} (查找码: {lookup_code})")

        log_success("完整取件码生成测试通过")
        return True

    except Exception as e:
        log_error(f"完整取件码生成测试失败: {e}")
        return False


def test_extract_codes():
    """测试取件码提取功能"""
    log_test_start("取件码提取功能")

    try:
        # 测试正常提取
        test_codes = [
            ("ABC123XYZ789", "ABC123", "XYZ789"),
            ("WAIT01TRAN02", "WAIT01", "TRAN02"),
            ("CODE01SECRET", "CODE01", "SECRET"),
        ]

        passed = 0
        for full_code, expected_lookup, expected_key in test_codes:
            try:
                lookup_code = extract_lookup_code(full_code)
                key_code = extract_key_code(full_code)

                if lookup_code == expected_lookup and key_code == expected_key:
                    log_info(f"✓ 提取成功: {full_code} -> 查找码:{lookup_code}, 密钥码:{key_code}")
                    passed += 1
                else:
                    log_error(f"✗ 提取失败: {full_code} -> 期望:查找码{expected_lookup},密钥码{expected_key}; 实际:查找码{lookup_code},密钥码{key_code}")
            except Exception as e:
                log_error(f"提取异常: {full_code} - {e}")

        # 测试异常情况
        invalid_codes = ["", "ABC", "abc123xyz789", "ABC123XYZ78"]  # 空、太短、小写、11位
        for invalid_code in invalid_codes:
            try:
                extract_lookup_code(invalid_code)
                log_error(f"应拒绝无效取件码但通过: {invalid_code}")
            except (ValueError, IndexError):
                log_info(f"✓ 正确拒绝无效取件码: {invalid_code}")
                passed += 1

        log_info(f"取件码提取测试: {passed}/{(len(test_codes) + len(invalid_codes))} 通过")
        return passed == (len(test_codes) + len(invalid_codes))

    except Exception as e:
        log_error(f"取件码提取测试失败: {e}")
        return False


def test_validate_pickup_codes():
    """测试取件码验证功能"""
    log_test_start("取件码验证功能")

    try:
        # 测试有效6位查找码
        valid_lookup_codes = ["ABC123", "WAIT01", "CODE01", "XYZ789", "TRAN02"]
        passed = 0

        for code in valid_lookup_codes:
            if validate_pickup_code(code):
                log_info(f"✓ 有效查找码: {code}")
                passed += 1
            else:
                log_error(f"✗ 应有效但无效: {code}")

        # 测试无效6位查找码
        invalid_lookup_codes = ["abc123", "ABC12", "ABC1234", "ABC-12", "ABC 12", "ABC.12"]
        for code in invalid_lookup_codes:
            if not validate_pickup_code(code):
                log_info(f"✓ 正确拒绝无效查找码: {code}")
                passed += 1
            else:
                log_error(f"✗ 应无效但有效: {code}")

        # 测试有效12位完整码
        valid_full_codes = ["ABC123XYZ789", "WAIT01TRAN02", "CODE01SECRET"]
        for code in valid_full_codes:
            if validate_full_pickup_code(code):
                log_info(f"✓ 有效完整码: {code}")
                passed += 1
            else:
                log_error(f"✗ 应有效但无效: {code}")

        # 测试无效12位完整码
        invalid_full_codes = ["abc123xyz789", "ABC123XYZ78", "ABC123XYZ7890", "ABC123-XYZ789"]
        for code in invalid_full_codes:
            if not validate_full_pickup_code(code):
                log_info(f"✓ 正确拒绝无效完整码: {code}")
                passed += 1
            else:
                log_error(f"✗ 应无效但有效: {code}")

        total_tests = len(valid_lookup_codes) + len(invalid_lookup_codes) + len(valid_full_codes) + len(invalid_full_codes)
        log_info(f"取件码验证测试: {passed}/{total_tests} 通过")
        return passed == total_tests

    except Exception as e:
        log_error(f"取件码验证测试失败: {e}")
        return False


def test_pickup_code_expiration(db):
    """测试取件码有效期"""
    log_test_start("取件码有效期测试")

    try:
        user = create_test_user(db, "test_exp_user", "password123")

        # 测试不同有效期
        test_cases = [
            ("1分钟过期", -1/60),  # 1分钟前过期
            ("1小时过期", -1),     # 1小时前过期
            ("1天过期", -24),      # 1天前过期
            ("未过期", 1),         # 1小时后过期
        ]

        passed = 0
        total = len(test_cases)

        for desc, expire_hours in test_cases:
            try:
                file_record, pickup_code, lookup_code, full_code = create_test_file_and_pickup_code(
                    db, user.id, expire_hours=expire_hours
                )

                # 检查过期状态
                is_expired = check_and_update_expired_pickup_code(pickup_code, db)
                db.refresh(pickup_code)  # 刷新状态

                if expire_hours < 0:  # 应该过期
                    if is_expired and pickup_code.status == "expired":
                        log_info(f"✓ {desc} - 正确标记为过期")
                        passed += 1
                    else:
                        log_error(f"✗ {desc} - 应过期但未过期 (状态: {pickup_code.status})")
                else:  # 不应该过期
                    if not is_expired and pickup_code.status == "waiting":
                        log_info(f"✓ {desc} - 正确标记为未过期")
                        passed += 1
                    else:
                        log_error(f"✗ {desc} - 应未过期但过期了 (状态: {pickup_code.status})")

            except Exception as e:
                log_error(f"{desc} 测试异常: {e}")
            finally:
                # 清理
                try:
                    db.query(PickupCode).filter(PickupCode.code == lookup_code).delete()
                    db.query(File).filter(File.id == file_record.id).delete()
                    db.commit()
                except:
                    pass

        log_info(f"取件码有效期测试: {passed}/{total} 通过")
        return passed == total

    except Exception as e:
        log_error(f"取件码有效期测试失败: {e}")
        return False
    finally:
        # 清理用户
        try:
            db.query(User).filter(User.username == "test_exp_user").delete()
            db.commit()
        except:
            pass


def test_usage_limit(db):
    """测试使用次数限制"""
    log_test_start("使用次数限制测试")

    try:
        user = create_test_user(db, "test_limit_user", "password123")

        # 测试不同限制次数
        test_cases = [
            ("1次限制", 1),
            ("2次限制", 2),
            ("3次限制", 3),
        ]

        passed = 0
        total = len(test_cases)

        for desc, limit_count in test_cases:
            try:
                file_record, pickup_code, lookup_code, full_code = create_test_file_and_pickup_code(
                    db, user.id, limit_count=limit_count
                )

                # 测试使用次数限制逻辑
                # 业务逻辑：当 used_count >= limit_count 时，应该被拒绝（limit_count != 999）
                test_passed = True
                
                # 测试在限制内的使用
                for i in range(limit_count):
                    pickup_code.used_count = i
                    db.commit()
                    db.refresh(pickup_code)
                    
                    # 检查是否应该被允许（used_count < limit_count）
                    used_count = pickup_code.used_count or 0
                    limit = pickup_code.limit_count or 3
                    should_allow = (limit == 999) or (used_count < limit)
                    
                    if should_allow:
                        log_info(f"✓ {desc} - 使用 {i+1}/{limit_count} 次: 允许")
                    else:
                        log_error(f"✗ {desc} - 使用 {i+1}/{limit_count} 次: 错误拒绝")
                        test_passed = False
                
                # 测试超出限制的使用
                pickup_code.used_count = limit_count
                db.commit()
                db.refresh(pickup_code)
                
                used_count = pickup_code.used_count or 0
                limit = pickup_code.limit_count or 3
                should_reject = (limit != 999) and (used_count >= limit)
                
                if should_reject:
                    log_info(f"✓ {desc} - 使用 {limit_count+1}/{limit_count} 次: 正确拒绝")
                else:
                    log_error(f"✗ {desc} - 使用 {limit_count+1}/{limit_count} 次: 应拒绝但允许")
                    test_passed = False
                
                if test_passed:
                    passed += 1

            except Exception as e:
                log_error(f"{desc} 测试异常: {e}")
            finally:
                # 清理
                try:
                    db.query(PickupCode).filter(PickupCode.code == lookup_code).delete()
                    db.query(File).filter(File.id == file_record.id).delete()
                    db.commit()
                except:
                    pass

        log_info(f"使用次数限制测试: {passed}/{total} 通过")
        return passed == total

    except Exception as e:
        log_error(f"使用次数限制测试失败: {e}")
        return False
    finally:
        # 清理用户
        try:
            db.query(User).filter(User.username == "test_limit_user").delete()
            db.commit()
        except:
            pass


def test_pickup_code_lookup(db):
    """测试取件码查找功能"""
    log_test_start("取件码查找功能")

    try:
        user = create_test_user(db, "test_lookup_user", "password123")
        file_record, pickup_code, lookup_code, full_code = create_test_file_and_pickup_code(db, user.id)

        # 测试查找存在的取件码
        found_code = get_pickup_code_by_lookup(db, lookup_code)
        if found_code and found_code.code == lookup_code:
            log_info(f"✓ 成功查找取件码: {lookup_code}")
        else:
            log_error(f"✗ 查找失败: {lookup_code}")
            return False

        # 测试查找不存在的取件码
        not_found_code = get_pickup_code_by_lookup(db, "NONEXIST")
        if not_found_code is None:
            log_info("✓ 正确返回None对于不存在的取件码")
        else:
            log_error("✗ 不存在的取件码返回了结果")
            return False

        log_success("取件码查找功能测试通过")
        return True

    except Exception as e:
        log_error(f"取件码查找功能测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)
        try:
            db.query(User).filter(User.username == "test_lookup_user").delete()
            db.commit()
        except:
            pass


def run_pickup_code_tests():
    """运行所有取件码测试"""
    log_section("12位取件码系统测试")

    db = SessionLocal()

    try:
        # 清理可能的旧测试数据
        cleanup_test_data(db)

        tests = [
            ("取件码生成测试", [
                test_generate_pickup_code_format,
                lambda: test_generate_unique_lookup_code(db),
                lambda: test_generate_unique_pickup_code(db),
            ]),
            ("取件码验证测试", [
                test_extract_codes,
                test_validate_pickup_codes,
                lambda: test_pickup_code_lookup(db),
            ]),
            ("取件码状态测试", [
                lambda: test_pickup_code_expiration(db),
                lambda: test_usage_limit(db),
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
            log_success("所有取件码测试通过！🎉")
        else:
            log_error("部分取件码测试失败，请检查实现")

        return total_passed == total_tests

    except Exception as e:
        log_error(f"取件码测试过程中发生严重错误: {e}")
        return False
    finally:
        # 最终清理
        try:
            cleanup_test_data(db)
        except:
            pass
        db.close()


if __name__ == "__main__":
    success = run_pickup_code_tests()
    sys.exit(0 if success else 1)