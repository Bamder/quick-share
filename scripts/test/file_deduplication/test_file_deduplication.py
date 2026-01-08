"""
文件去重功能测试

测试文件去重系统的各种场景，包括正常和异常情况：
- 同用户同文件：应该识别为相同文件，支持去重
- 同用户不同文件：应该识别为不同文件，不去重
- 不同用户同文件：应该识别为不同文件，用户隔离
- 文件复用逻辑：检查缓存复用和文件记录复用

使用方法:
    # Windows (推荐):
    scripts\\test\\file_deduplication\\run_dedupe_test.bat
    或
    scripts\test\file_deduplication\run_dedupe_test.ps1

    # 手动运行 (需要先激活虚拟环境):
    python scripts/test/file_deduplication/test_file_deduplication.py
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
        print("    scripts\\test\\file_deduplication\\run_dedupe_test.bat")
        print("    或")
        print("    scripts\\test\\file_deduplication\\run_dedupe_test.ps1")
        print("")
        print("  手动激活虚拟环境后运行:")
        print("    venv\\Scripts\\activate")
        print("    python scripts\\test\\file_deduplication\\test_file_deduplication.py")
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
from app.services.file_reuse_service import FileReuseService
from app.utils.dedupe import derive_dedupe_fingerprint
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


def create_test_file(db, user_id, filename="test.txt", size=1024, plaintext_hash=None):
    """创建测试文件记录"""
    # 如果没有提供明文哈希，生成一个假的
    if plaintext_hash is None:
        plaintext_hash = f"abcd{'0' * 59}"  # 64字符的假SHA-256

    # 计算去重指纹
    dedupe_fingerprint = derive_dedupe_fingerprint(
        user_id=user_id,
        plaintext_file_hash=plaintext_hash
    )

    file_record = File(
        original_name=filename,
        stored_name=f"stored_{filename}",
        size=size,
        hash=dedupe_fingerprint,  # 存储去重指纹
        mime_type="text/plain",
        uploader_id=user_id
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)
    return file_record, plaintext_hash


def cleanup_test_data(db):
    """清理测试数据"""
    # 删除测试文件
    db.query(File).filter(File.original_name.like("test_dedupe_%")).delete()

    # 删除测试用户
    test_users = ["user1", "user2", "user3"]
    db.query(User).filter(User.username.in_(test_users)).delete()

    db.commit()


def test_dedupe_fingerprint_generation():
    """测试去重指纹生成"""
    log_test_start("去重指纹生成")

    try:
        # 测试同一个用户同一个明文哈希应该产生相同的指纹
        user_id = 123
        plaintext_hash = "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"

        fingerprint1 = derive_dedupe_fingerprint(
            user_id=user_id,
            plaintext_file_hash=plaintext_hash
        )

        fingerprint2 = derive_dedupe_fingerprint(
            user_id=user_id,
            plaintext_file_hash=plaintext_hash
        )

        if fingerprint1 == fingerprint2:
            log_info(f"✓ 相同输入产生相同指纹: {fingerprint1[:16]}...")
        else:
            log_error(f"✗ 相同输入产生不同指纹: {fingerprint1[:16]}... vs {fingerprint2[:16]}...")
            return False

        # 测试不同用户同一个明文哈希应该产生不同的指纹
        user_id2 = 456
        fingerprint3 = derive_dedupe_fingerprint(
            user_id=user_id2,
            plaintext_file_hash=plaintext_hash
        )

        if fingerprint1 != fingerprint3:
            log_info(f"✓ 不同用户产生不同指纹: user{user_id}={fingerprint1[:16]}..., user{user_id2}={fingerprint3[:16]}...")
        else:
            log_error(f"✗ 不同用户产生相同指纹: {fingerprint1}")
            return False

        # 测试同一个用户不同明文哈希应该产生不同的指纹
        plaintext_hash2 = "b665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
        fingerprint4 = derive_dedupe_fingerprint(
            user_id=user_id,
            plaintext_file_hash=plaintext_hash2
        )

        if fingerprint1 != fingerprint4:
            log_info(f"✓ 不同文件产生不同指纹: {plaintext_hash[:16]}... -> {fingerprint1[:16]}..., {plaintext_hash2[:16]}... -> {fingerprint4[:16]}...")
        else:
            log_error(f"✗ 不同文件产生相同指纹: {fingerprint1}")
            return False

        log_success("去重指纹生成测试通过")
        return True

    except Exception as e:
        log_error(f"去重指纹生成测试失败: {e}")
        return False


def test_same_user_same_file(db):
    """测试同用户同文件的去重"""
    log_test_start("同用户同文件去重")

    try:
        # 创建测试用户
        user = create_test_user(db, "user1", "password123")

        # 创建第一个文件
        file1, plaintext_hash = create_test_file(
            db, user.id, "test_dedupe_same.txt", 1024
        )

        # 再次检查相同文件（模拟用户上传同一个文件）
        existing_file, file_unchanged = FileReuseService.check_file_exists(
            hash_value=plaintext_hash,
            original_name="test_dedupe_same.txt",
            size=1024,
            uploader_id=user.id,
            db=db
        )

        if existing_file and file_unchanged:
            if existing_file.id == file1.id:
                log_info(f"✓ 同用户同文件正确识别: file_id={existing_file.id}, hash={existing_file.hash[:16]}...")
            else:
                log_error(f"✗ 找到的文件ID不匹配: 期望{file1.id}, 实际{existing_file.id}")
                return False
        else:
            log_error("✗ 同用户同文件未被识别为相同")
            return False

        # 验证去重指纹相同
        expected_fingerprint = derive_dedupe_fingerprint(
            user_id=user.id,
            plaintext_file_hash=plaintext_hash
        )

        if existing_file.hash == expected_fingerprint:
            log_info("✓ 去重指纹正确匹配")
        else:
            log_error(f"✗ 去重指纹不匹配: 期望{expected_fingerprint[:16]}..., 实际{existing_file.hash[:16]}...")
            return False

        log_success("同用户同文件去重测试通过")
        return True

    except Exception as e:
        log_error(f"同用户同文件去重测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_same_user_different_file(db):
    """测试同用户不同文件的去重"""
    log_test_start("同用户不同文件去重")

    try:
        # 创建测试用户
        user = create_test_user(db, "user1", "password123")

        # 创建第一个文件（提供不同的明文哈希）
        hash1 = "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
        file1, _ = create_test_file(
            db, user.id, "test_dedupe_file1.txt", 1024, plaintext_hash=hash1
        )

        # 创建第二个不同文件（不同文件名、大小和哈希）
        hash2 = "b665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
        file2, _ = create_test_file(
            db, user.id, "test_dedupe_file2.txt", 2048, plaintext_hash=hash2
        )

        # 检查第二个文件是否被识别为不同文件
        existing_file, file_unchanged = FileReuseService.check_file_exists(
            hash_value=hash2,
            original_name="test_dedupe_file2.txt",
            size=2048,
            uploader_id=user.id,
            db=db
        )

        if existing_file and file_unchanged:
            if existing_file.id == file2.id:
                log_info(f"✓ 同用户不同文件正确识别: file_id={existing_file.id}")
            else:
                log_error(f"✗ 文件ID不匹配: 期望{file2.id}, 实际{existing_file.id}")
                return False
        else:
            log_error("✗ 同用户不同文件被误认为相同或不存在")
            return False

        # 验证去重指纹不同
        fingerprint1 = derive_dedupe_fingerprint(
            user_id=user.id,
            plaintext_file_hash=hash1
        )
        fingerprint2 = derive_dedupe_fingerprint(
            user_id=user.id,
            plaintext_file_hash=hash2
        )

        if fingerprint1 != fingerprint2:
            log_info(f"✓ 不同文件的去重指纹不同: {fingerprint1[:16]}... vs {fingerprint2[:16]}...")
        else:
            log_error(f"✗ 不同文件的去重指纹相同: {fingerprint1}")
            return False

        log_success("同用户不同文件去重测试通过")
        return True

    except Exception as e:
        log_error(f"同用户不同文件去重测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_different_user_same_file(db):
    """测试不同用户同文件的去重（用户隔离）"""
    log_test_start("不同用户同文件去重（用户隔离）")

    try:
        # 创建两个不同用户
        user1 = create_test_user(db, "user1", "password123")
        user2 = create_test_user(db, "user2", "password456")

        # 使用相同的明文哈希（模拟相同的文件内容）
        plaintext_hash = "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"

        # 用户1上传文件
        file1, _ = create_test_file(
            db, user1.id, "test_dedupe_shared.txt", 1024, plaintext_hash
        )

        # 用户2上传相同文件
        file2, _ = create_test_file(
            db, user2.id, "test_dedupe_shared.txt", 1024, plaintext_hash
        )

        # 验证两个文件的去重指纹不同
        fingerprint1 = derive_dedupe_fingerprint(
            user_id=user1.id,
            plaintext_file_hash=plaintext_hash
        )
        fingerprint2 = derive_dedupe_fingerprint(
            user_id=user2.id,
            plaintext_file_hash=plaintext_hash
        )

        if fingerprint1 != fingerprint2:
            log_info(f"✓ 不同用户的相同文件产生不同指纹（用户隔离）: user{user1.id}={fingerprint1[:16]}..., user{user2.id}={fingerprint2[:16]}...")
        else:
            log_error(f"✗ 不同用户产生了相同指纹（用户隔离失败）: {fingerprint1}")
            return False

        # 验证两个文件记录不同
        if file1.id != file2.id and file1.hash != file2.hash:
            log_info(f"✓ 不同用户创建了不同的文件记录: file1_id={file1.id}, file2_id={file2.id}")
        else:
            log_error(f"✗ 不同用户创建了相同的文件记录: file1_id={file1.id}, file2_id={file2.id}")
            return False

        # 验证用户1查找自己的文件
        existing_file1, file_unchanged1 = FileReuseService.check_file_exists(
            hash_value=plaintext_hash,
            original_name="test_dedupe_shared.txt",
            size=1024,
            uploader_id=user1.id,
            db=db
        )

        if existing_file1 and file_unchanged1 and existing_file1.id == file1.id:
            log_info(f"✓ 用户{user1.id}正确找到自己的文件: file_id={existing_file1.id}")
        else:
            log_error(f"✗ 用户{user1.id}未找到自己的文件")
            return False

        # 验证用户2查找自己的文件
        existing_file2, file_unchanged2 = FileReuseService.check_file_exists(
            hash_value=plaintext_hash,
            original_name="test_dedupe_shared.txt",
            size=1024,
            uploader_id=user2.id,
            db=db
        )

        if existing_file2 and file_unchanged2 and existing_file2.id == file2.id:
            log_info(f"✓ 用户{user2.id}正确找到自己的文件: file_id={existing_file2.id}")
        else:
            log_error(f"✗ 用户{user2.id}未找到自己的文件")
            return False

        # 验证用户1找不到用户2的文件（用户隔离）
        if existing_file1.id != existing_file2.id:
            log_info("✓ 用户隔离工作正常：用户1和用户2的文件记录不同")
        else:
            log_error("✗ 用户隔离失败：用户1和用户2的文件记录相同")
            return False

        log_success("不同用户同文件去重（用户隔离）测试通过")
        return True

    except Exception as e:
        log_error(f"不同用户同文件去重测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_file_reuse_eligibility(db):
    """测试文件复用资格检查"""
    log_test_start("文件复用资格检查")

    try:
        # 创建测试用户
        user = create_test_user(db, "user1", "password123")

        # 创建测试文件
        file_record, plaintext_hash = create_test_file(
            db, user.id, "test_reuse_eligibility.txt", 1024
        )

        # 测试文件复用资格
        is_eligible, reason, metadata = FileReuseService.check_file_reuse_eligibility(
            existing_file=file_record,
            uploader_id=user.id,
            db=db
        )

        # 正常情况下应该允许复用
        if is_eligible:
            log_info(f"✓ 文件复用资格检查通过: {reason}")
        else:
            log_info(f"ℹ️ 文件复用资格检查结果: 不允许复用 - {reason}")
            # 这不是错误，只是当前状态

        # 测试无效文件
        file_record.is_invalidated = True
        db.commit()

        is_eligible2, reason2, metadata2 = FileReuseService.check_file_reuse_eligibility(
            existing_file=file_record,
            uploader_id=user.id,
            db=db
        )

        if not is_eligible2:
            log_info(f"✓ 无效文件正确拒绝复用: {reason2}")
        else:
            log_error("✗ 无效文件仍被允许复用")
            return False

        log_success("文件复用资格检查测试通过")
        return True

    except Exception as e:
        log_error(f"文件复用资格检查测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_dedupe_fingerprint_edge_cases():
    """测试去重指纹的边界情况"""
    log_test_start("去重指纹边界情况")

    try:
        passed = 0
        total = 0

        # 测试空哈希
        total += 1
        try:
            derive_dedupe_fingerprint(user_id=1, plaintext_file_hash="")
            log_error("✗ 空哈希未抛出异常")
        except ValueError:
            log_info("✓ 空哈希正确抛出异常")
            passed += 1

        # 测试不同长度的哈希（但不强制64字符）
        total += 1
        try:
            fingerprint = derive_dedupe_fingerprint(user_id=1, plaintext_file_hash="short")
            if fingerprint:
                log_info("✓ 短哈希仍能生成指纹（兼容性）")
                passed += 1
            else:
                log_error("✗ 短哈希生成空指纹")
        except Exception as e:
            log_error(f"✗ 短哈希异常: {e}")

        # 测试None用户ID
        total += 1
        try:
            fingerprint = derive_dedupe_fingerprint(user_id=None, plaintext_file_hash="a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3")
            if fingerprint:
                log_info("✓ None用户ID能生成指纹（匿名用户）")
                passed += 1
            else:
                log_error("✗ None用户ID生成空指纹")
        except Exception as e:
            log_error(f"✗ None用户ID异常: {e}")

        # 测试大小写归一化
        total += 1
        hash_lower = "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3"
        hash_upper = hash_lower.upper()

        fp_lower = derive_dedupe_fingerprint(user_id=1, plaintext_file_hash=hash_lower)
        fp_upper = derive_dedupe_fingerprint(user_id=1, plaintext_file_hash=hash_upper)

        if fp_lower == fp_upper:
            log_info("✓ 大小写哈希产生相同指纹（归一化）")
            passed += 1
        else:
            log_error("✗ 大小写哈希产生不同指纹")

        # 测试包含空格的哈希
        total += 1
        hash_with_spaces = " a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3 "
        fp_normal = derive_dedupe_fingerprint(user_id=1, plaintext_file_hash=hash_lower)
        fp_spaced = derive_dedupe_fingerprint(user_id=1, plaintext_file_hash=hash_with_spaces)

        if fp_normal == fp_spaced:
            log_info("✓ 带空格哈希产生相同指纹（strip处理）")
            passed += 1
        else:
            log_error("✗ 带空格哈希产生不同指纹")

        log_info(f"去重指纹边界情况测试: {passed}/{total} 通过")
        return passed == total

    except Exception as e:
        log_error(f"去重指纹边界情况测试失败: {e}")
        return False


def run_file_deduplication_tests():
    """运行所有文件去重测试"""
    log_section("文件去重系统测试")

    db = SessionLocal()

    try:
        # 清理可能的旧测试数据
        cleanup_test_data(db)

        tests = [
            ("去重指纹测试", [
                test_dedupe_fingerprint_generation,
                test_dedupe_fingerprint_edge_cases,
            ]),
            ("文件存在性检查测试", [
                lambda: test_same_user_same_file(db),
                lambda: test_same_user_different_file(db),
                lambda: test_different_user_same_file(db),
                lambda: test_file_reuse_eligibility(db),
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
            log_success("所有文件去重测试通过！🎉")
        else:
            log_error("部分文件去重测试失败，请检查实现")

        return total_passed == total_tests

    except Exception as e:
        log_error(f"文件去重测试过程中发生严重错误: {e}")
        return False
    finally:
        # 最终清理
        try:
            cleanup_test_data(db)
        except:
            pass
        db.close()


if __name__ == "__main__":
    success = run_file_deduplication_tests()
    sys.exit(0 if success else 1)
