"""
文件上传/下载功能测试

测试文件操作系统的各种场景，包括正常和异常情况：
- 文件上传：分块上传、完成上传、各种文件格式和大小
- 文件下载：获取文件信息、下载块、完成下载
- 异常情况：权限不足、文件不存在、取件码过期等

使用方法:
    # Windows (推荐):
    scripts\\test\\file_operations\\run_file_test.bat
    或
    scripts\test\file_operations\run_file_test.ps1

    # 手动运行 (需要先激活虚拟环境):
    python scripts/test/file_operations/test_file_operations.py
"""

import sys
import os
from pathlib import Path
import io
from unittest.mock import Mock, AsyncMock
import hashlib
from datetime import datetime, timedelta, timezone

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
        print("    scripts\\test\\file_operations\\run_file_test.bat")
        print("    或")
        print("    scripts\\test\\file_operations\\run_file_test.ps1")
        print("")
        print("  手动激活虚拟环境后运行:")
        print("    venv\\Scripts\\activate")
        print("    python scripts\\test\\file_operations\\test_file_operations.py")
        print("=" * 60)
        print("")

        # 在非交互式环境中自动继续
        if not sys.stdin.isatty():
            print("非交互式环境，自动继续...")
            return False
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
from app.services.cache_service import chunk_cache, file_info_cache, encrypted_key_cache
from app.services.upload_service import upload_chunk as upload_chunk_service, upload_complete as upload_complete_service
from app.services.download_service import (
    download_chunk as download_chunk_service,
    download_complete as download_complete_service,
    get_file_info as get_file_info_service
)
import logging

# 导入测试工具
sys.path.insert(0, str(Path(__file__).parent.parent))
from test_utils import *

# 配置日志输出到控制台
logging.basicConfig(level=logging.INFO, format='%(message)s')

logger = logging.getLogger(__name__)


def create_test_user(db, username="test_user", password="test_password"):
    """创建测试用户"""
    from app.routes.auth import hash_password
    password_hash = hash_password(password)
    user = User(
        username=username,
        password_hash=password_hash
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_pickup_code(db, user_id, expire_hours=24, limit_count=3):
    """创建测试取件码"""
    from app.utils.pickup_code import generate_unique_pickup_code, DatetimeUtil

    # 生成取件码
    lookup_code, full_code = generate_unique_pickup_code(db)

    # 创建文件记录
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

    # 创建取件码记录
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

    return lookup_code, full_code, file_record, pickup_code


def cleanup_test_data(db):
    """清理测试数据"""
    # 删除测试取件码
    test_codes = ["TESTUP01", "TESTUP02", "TESTUP03", "TESTDL01", "TESTDL02", "TESTDL03"]
    db.query(PickupCode).filter(PickupCode.code.in_(test_codes)).delete()

    # 删除测试文件
    db.query(File).filter(File.original_name.like("test_file_%")).delete()

    # 删除测试用户
    test_users = ["test_upload_user", "test_download_user", "test_expired_user"]
    db.query(User).filter(User.username.in_(test_users)).delete()

    db.commit()


def create_mock_upload_file(content, filename="test.txt", content_type="text/plain"):
    """创建模拟的上传文件"""
    file_content = io.BytesIO(content)
    upload_file = Mock(spec=UploadFile)
    upload_file.filename = filename
    upload_file.content_type = content_type
    upload_file.file = file_content
    upload_file.read = AsyncMock(return_value=content)
    upload_file.seek = AsyncMock()
    upload_file.close = AsyncMock()
    return upload_file


def test_upload_chunk_normal(db):
    """测试正常文件块上传"""
    log_test_start("正常文件块上传")

    try:
        # 创建测试用户和取件码
        user = create_test_user(db, "test_upload_user", "password123")
        lookup_code, full_code, file_record, pickup_code = create_test_pickup_code(db, user.id)

        # 模拟文件块数据
        chunk_data = b"Hello, this is test chunk data!" * 100  # 约2.8KB
        upload_file = create_mock_upload_file(chunk_data, "chunk_0.txt")

        # 上传文件块
        from fastapi import Request
        request = Mock(spec=Request)

        # 注意：这里需要使用 await，因为服务函数是 async 的
        import asyncio
        result = asyncio.run(upload_chunk_service(
            code=lookup_code,
            chunk_data=upload_file,
            chunk_index=0,
            chunk_index_query=0,
            db=db,
            current_user=user
        ))

        # 验证结果
        if hasattr(result, 'status_code') and result.status_code == 200:
            log_success("文件块上传成功")
            return True
        else:
            log_error(f"文件块上传失败: {result}")
            return False

    except Exception as e:
        log_error(f"正常文件块上传测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_upload_chunk_unauthorized(db):
    """测试未授权用户上传文件块"""
    log_test_start("未授权用户上传文件块")

    try:
        # 创建测试用户和取件码
        user = create_test_user(db, "test_upload_user", "password123")
        lookup_code, full_code, file_record, pickup_code = create_test_pickup_code(db, user.id)

        # 模拟文件块数据
        chunk_data = b"Unauthorized chunk data"
        upload_file = create_mock_upload_file(chunk_data)

        # 尝试使用 None 用户上传（未登录）
        import asyncio
        result = asyncio.run(upload_chunk_service(
            code=lookup_code,
            chunk_data=upload_file,
            chunk_index=0,
            chunk_index_query=0,
            db=db,
            current_user=None  # 未登录用户
        ))

        # 验证结果 - 应该返回错误
        if hasattr(result, 'status_code') and result.status_code == 400:
            log_success("正确拒绝未授权用户上传")
            return True
        else:
            log_error(f"未正确拒绝未授权用户: {result}")
            return False

    except Exception as e:
        log_error(f"未授权用户上传测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_upload_chunk_invalid_code(db):
    """测试无效取件码上传文件块"""
    log_test_start("无效取件码上传文件块")

    try:
        # 创建测试用户
        user = create_test_user(db, "test_upload_user", "password123")

        # 模拟文件块数据
        chunk_data = b"Invalid code chunk data"
        upload_file = create_mock_upload_file(chunk_data)

        # 使用无效取件码上传
        import asyncio
        result = asyncio.run(upload_chunk_service(
            code="INVALID",  # 无效取件码
            chunk_data=upload_file,
            chunk_index=0,
            chunk_index_query=0,
            db=db,
            current_user=user
        ))

        # 验证结果 - 应该返回错误
        if hasattr(result, 'status_code') and result.status_code in [400, 404]:
            log_success("正确拒绝无效取件码")
            return True
        else:
            log_error(f"未正确拒绝无效取件码: {result}")
            return False

    except Exception as e:
        log_error(f"无效取件码上传测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_upload_complete_normal(db):
    """测试正常上传完成"""
    log_test_start("正常上传完成")

    try:
        # 创建测试用户和取件码
        user = create_test_user(db, "test_upload_user", "password123")
        lookup_code, full_code, file_record, pickup_code = create_test_pickup_code(db, user.id)

        # 先上传一个文件块
        chunk_data = b"Hello, this is test chunk data!" * 10
        upload_file = create_mock_upload_file(chunk_data, "chunk_0.txt")

        import asyncio
        upload_result = asyncio.run(upload_chunk_service(
            code=lookup_code,
            chunk_data=upload_file,
            chunk_index=0,
            chunk_index_query=0,
            db=db,
            current_user=user
        ))

        if not (hasattr(upload_result, 'status_code') and upload_result.status_code == 200):
            log_error("文件块上传失败，无法进行完成测试")
            return False

        # 上传完成
        from app.schemas.request import UploadCompleteRequest
        complete_request = UploadCompleteRequest(
            totalChunks=1,
            fileSize=len(chunk_data),
            fileName="test_file.txt",
            mimeType="text/plain"
        )

        complete_result = asyncio.run(upload_complete_service(
            code=lookup_code,
            request=complete_request,
            db=db,
            current_user=user
        ))

        # 验证结果
        if hasattr(complete_result, 'status_code') and complete_result.status_code == 200:
            log_success("上传完成成功")
            return True
        else:
            log_error(f"上传完成失败: {complete_result}")
            return False

    except Exception as e:
        log_error(f"正常上传完成测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_upload_different_file_sizes(db):
    """测试不同文件大小的上传"""
    log_test_start("不同文件大小上传")

    test_cases = [
        ("小文件", 1024, "text/plain"),  # 1KB
        ("中等文件", 1024 * 1024, "application/pdf"),  # 1MB
        ("大文件", 10 * 1024 * 1024, "application/zip"),  # 10MB (模拟)
    ]

    passed = 0
    total = len(test_cases)

    for size_name, size, mime_type in test_cases:
        try:
            log_info(f"测试 {size_name} ({size} 字节)")

            # 创建测试用户和取件码
            user = create_test_user(db, f"test_size_user_{passed}", "password123")
            lookup_code, full_code, file_record, pickup_code = create_test_pickup_code(db, user.id)

            # 生成相应大小的文件数据
            chunk_data = b"X" * min(size, 1024 * 1024)  # 限制实际生成的数据大小
            upload_file = create_mock_upload_file(chunk_data, f"test_{size_name}.dat", mime_type)

            import asyncio
            result = asyncio.run(upload_chunk_service(
                code=lookup_code,
                chunk_data=upload_file,
                chunk_index=0,
                chunk_index_query=0,
                db=db,
                current_user=user
            ))

            if hasattr(result, 'status_code') and result.status_code == 200:
                log_success(f"{size_name} 上传成功")
                passed += 1
            else:
                log_error(f"{size_name} 上传失败: {result}")

        except Exception as e:
            log_error(f"{size_name} 上传测试异常: {e}")
        finally:
            # 清理当前测试的数据
            try:
                db.query(PickupCode).filter(PickupCode.code == lookup_code).delete()
                db.query(File).filter(File.id == file_record.id).delete()
                db.query(User).filter(User.username == f"test_size_user_{passed-1}").delete()
                db.commit()
            except:
                pass

    log_info(f"不同文件大小测试: {passed}/{total} 通过")
    return passed == total


def test_upload_different_file_types(db):
    """测试不同文件类型的上传"""
    log_test_start("不同文件类型上传")

    test_cases = [
        ("文本文件", "text/plain", b"Hello, World!\nThis is a test file."),
        ("JSON文件", "application/json", b'{"key": "value", "number": 123}'),
        ("图片文件", "image/jpeg", b'\xff\xd8\xff\xe0\x00\x10JFIF'),  # JPEG文件头
        ("PDF文件", "application/pdf", b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n'),  # PDF文件头
        ("ZIP文件", "application/zip", b'PK\x03\x04\x14\x00\x00\x00\x00\x00'),  # ZIP文件头
    ]

    passed = 0
    total = len(test_cases)

    for file_type, mime_type, content in test_cases:
        try:
            log_info(f"测试 {file_type}")

            # 创建测试用户和取件码
            user = create_test_user(db, f"test_type_user_{passed}", "password123")
            lookup_code, full_code, file_record, pickup_code = create_test_pickup_code(db, user.id)

            upload_file = create_mock_upload_file(content, f"test.{file_type.split()[0].lower()}", mime_type)

            import asyncio
            result = asyncio.run(upload_chunk_service(
                code=lookup_code,
                chunk_data=upload_file,
                chunk_index=0,
                chunk_index_query=0,
                db=db,
                current_user=user
            ))

            if hasattr(result, 'status_code') and result.status_code == 200:
                log_success(f"{file_type} 上传成功")
                passed += 1
            else:
                log_error(f"{file_type} 上传失败: {result}")

        except Exception as e:
            log_error(f"{file_type} 上传测试异常: {e}")
        finally:
            # 清理当前测试的数据
            try:
                db.query(PickupCode).filter(PickupCode.code == lookup_code).delete()
                db.query(File).filter(File.id == file_record.id).delete()
                db.query(User).filter(User.username == f"test_type_user_{passed-1}").delete()
                db.commit()
            except:
                pass

    log_info(f"不同文件类型测试: {passed}/{total} 通过")
    return passed == total


def test_download_file_info_normal(db):
    """测试正常获取文件信息"""
    log_test_start("正常获取文件信息")

    try:
        # 创建测试用户和取件码
        user = create_test_user(db, "test_download_user", "password123")
        lookup_code, full_code, file_record, pickup_code = create_test_pickup_code(db, user.id)

        # 上传文件块和完成上传
        chunk_data = b"Hello, this is test file content!"
        upload_file = create_mock_upload_file(chunk_data, "test.txt")

        import asyncio
        from app.schemas.request import UploadCompleteRequest

        # 上传块
        upload_result = asyncio.run(upload_chunk_service(
            code=lookup_code,
            chunk_data=upload_file,
            chunk_index=0,
            chunk_index_query=0,
            db=db,
            current_user=user
        ))

        # 完成上传
        complete_request = UploadCompleteRequest(
            totalChunks=1,
            fileSize=len(chunk_data),
            fileName="test_file.txt",
            mimeType="text/plain"
        )

        complete_result = asyncio.run(upload_complete_service(
            code=lookup_code,
            request=complete_request,
            db=db,
            current_user=user
        ))

        if not (hasattr(complete_result, 'status_code') and complete_result.status_code == 200):
            log_error("上传完成失败，无法进行下载测试")
            return False

        # 获取文件信息
        info_result = asyncio.run(get_file_info_service(code=lookup_code, db=db))

        # 验证结果
        if hasattr(info_result, 'status_code') and info_result.status_code == 200:
            log_success("获取文件信息成功")
            return True
        else:
            log_error(f"获取文件信息失败: {info_result}")
            return False

    except Exception as e:
        log_error(f"正常获取文件信息测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_download_chunk_normal(db):
    """测试正常下载文件块"""
    log_test_start("正常下载文件块")

    try:
        # 创建测试用户和取件码
        user = create_test_user(db, "test_download_user", "password123")
        lookup_code, full_code, file_record, pickup_code = create_test_pickup_code(db, user.id)

        # 上传文件块和完成上传
        chunk_data = b"Hello, this is test file content for download!"
        upload_file = create_mock_upload_file(chunk_data, "test.txt")

        import asyncio
        from app.schemas.request import UploadCompleteRequest

        # 上传块
        upload_result = asyncio.run(upload_chunk_service(
            code=lookup_code,
            chunk_data=upload_file,
            chunk_index=0,
            chunk_index_query=0,
            db=db,
            current_user=user
        ))

        # 完成上传
        complete_request = UploadCompleteRequest(
            totalChunks=1,
            fileSize=len(chunk_data),
            fileName="test_file.txt",
            mimeType="text/plain"
        )

        complete_result = asyncio.run(upload_complete_service(
            code=lookup_code,
            request=complete_request,
            db=db,
            current_user=user
        ))

        if not (hasattr(complete_result, 'status_code') and complete_result.status_code == 200):
            log_error("上传完成失败，无法进行下载测试")
            return False

        # 下载文件块
        download_result = asyncio.run(download_chunk_service(
            code=lookup_code,
            chunk_index=0,
            session_id=None,
            db=db
        ))

        # 验证结果
        if hasattr(download_result, 'status_code') and download_result.status_code == 200:
            log_success("下载文件块成功")
            return True
        else:
            log_error(f"下载文件块失败: {download_result}")
            return False

    except Exception as e:
        log_error(f"正常下载文件块测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_download_complete_normal(db):
    """测试正常下载完成"""
    log_test_start("正常下载完成")

    try:
        # 创建测试用户和取件码
        user = create_test_user(db, "test_download_user", "password123")
        lookup_code, full_code, file_record, pickup_code = create_test_pickup_code(db, user.id)

        # 上传文件块和完成上传
        chunk_data = b"Hello, this is test file content!"
        upload_file = create_mock_upload_file(chunk_data, "test.txt")

        import asyncio
        from app.schemas.request import UploadCompleteRequest

        # 上传块
        upload_result = asyncio.run(upload_chunk_service(
            code=lookup_code,
            chunk_data=upload_file,
            chunk_index=0,
            chunk_index_query=0,
            db=db,
            current_user=user
        ))

        # 完成上传
        complete_request = UploadCompleteRequest(
            totalChunks=1,
            fileSize=len(chunk_data),
            fileName="test_file.txt",
            mimeType="text/plain"
        )

        complete_result = asyncio.run(upload_complete_service(
            code=lookup_code,
            request=complete_request,
            db=db,
            current_user=user
        ))

        if not (hasattr(complete_result, 'status_code') and complete_result.status_code == 200):
            log_error("上传完成失败，无法进行下载完成测试")
            return False

        # 下载文件块（模拟下载过程）
        download_result = asyncio.run(download_chunk_service(
            code=lookup_code,
            chunk_index=0,
            session_id="test_session_123",
            db=db
        ))

        if not (hasattr(download_result, 'status_code') and download_result.status_code == 200):
            log_error("下载文件块失败，无法进行下载完成测试")
            return False

        # 完成下载
        from app.schemas.request import DownloadCompleteRequest
        complete_request = DownloadCompleteRequest(session_id="test_session_123")

        complete_result = asyncio.run(download_complete_service(
            code=lookup_code,
            session_id="test_session_123",
            db=db
        ))

        # 验证结果
        if hasattr(complete_result, 'status_code') and complete_result.status_code == 200:
            log_success("下载完成成功")
            return True
        else:
            log_error(f"下载完成失败: {complete_result}")
            return False

    except Exception as e:
        log_error(f"正常下载完成测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_download_expired_code(db):
    """测试下载过期取件码"""
    log_test_start("下载过期取件码")

    try:
        # 创建测试用户和过期的取件码
        user = create_test_user(db, "test_expired_user", "password123")
        lookup_code, full_code, file_record, pickup_code = create_test_pickup_code(db, user.id, expire_hours=-1)  # 已过期

        # 尝试下载文件块
        import asyncio
        download_result = asyncio.run(download_chunk_service(
            code=lookup_code,
            chunk_index=0,
            session_id=None,
            db=db
        ))

        # 验证结果 - 应该返回错误
        if hasattr(download_result, 'status_code') and download_result.status_code in [400, 404]:
            log_success("正确拒绝过期取件码下载")
            return True
        else:
            log_error(f"未正确拒绝过期取件码: {download_result}")
            return False

    except Exception as e:
        log_error(f"下载过期取件码测试失败: {e}")
        return False
    finally:
        # 清理
        cleanup_test_data(db)


def test_download_invalid_code(db):
    """测试下载无效取件码"""
    log_test_start("下载无效取件码")

    try:
        # 尝试下载无效取件码的文件块
        import asyncio
        download_result = asyncio.run(download_chunk_service(
            code="INVALID",  # 无效取件码
            chunk_index=0,
            session_id=None,
            db=db
        ))

        # 验证结果 - 应该返回错误
        if hasattr(download_result, 'status_code') and download_result.status_code in [400, 404]:
            log_success("正确拒绝无效取件码下载")
            return True
        else:
            log_error(f"未正确拒绝无效取件码: {download_result}")
            return False

    except Exception as e:
        log_error(f"下载无效取件码测试失败: {e}")
        return False


def run_file_operations_tests():
    """运行所有文件操作测试"""
    log_section("文件操作系统测试")

    db = SessionLocal()

    try:
        # 清理可能的旧测试数据
        cleanup_test_data(db)

        tests = [
            ("文件上传测试", [
                test_upload_chunk_normal,
                test_upload_chunk_unauthorized,
                test_upload_chunk_invalid_code,
                test_upload_complete_normal,
                test_upload_different_file_sizes,
                test_upload_different_file_types,
            ]),
            ("文件下载测试", [
                test_download_file_info_normal,
                test_download_chunk_normal,
                test_download_complete_normal,
                test_download_expired_code,
                test_download_invalid_code,
            ]),
        ]

        total_passed = 0
        total_tests = 0

        for section_name, section_tests in tests:
            log_subsection(f"{section_name} ({len(section_tests)} 个测试)")

            section_passed = 0
            for test_func in section_tests:
                try:
                    if test_func(db):
                        section_passed += 1
                        total_passed += 1
                    total_tests += 1
                except Exception as e:
                    log_error(f"测试 {test_func.__name__} 发生异常: {e}")
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
            log_success("所有文件操作测试通过！🎉")
        else:
            log_error("部分文件操作测试失败，请检查实现")

        return total_passed == total_tests

    except Exception as e:
        log_error(f"文件操作测试过程中发生严重错误: {e}")
        return False
    finally:
        # 最终清理
        try:
            cleanup_test_data(db)
        except:
            pass
        db.close()


if __name__ == "__main__":
    success = run_file_operations_tests()
    sys.exit(0 if success else 1)
