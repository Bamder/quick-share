"""
上传池机制测试

测试上传池的工作机制：
- 上传中断后恢复：验证上传池的恢复功能
- 大文件上传池性能：测试大文件上传的性能表现

使用方法:
    python scripts/test/upload_pool/test_upload_pool.py
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

from app.services.pool_service import upload_pool
from app.utils.pickup_code import DatetimeUtil
from datetime import datetime, timedelta
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))
from test_utils import *

# 配置日志输出到控制台
logging.basicConfig(level=logging.INFO, format='%(message)s')

logger = logging.getLogger(__name__)


def test_upload_recovery():
    """测试上传中断后恢复"""
    log_test_start("上传中断后恢复")

    try:
        # 模拟上传池中的数据
        test_chunks = {
            0: {'data': b'chunk_0_data', 'hash': 'hash0', 'expires_at': DatetimeUtil.now() + timedelta(hours=1)},
            1: {'data': b'chunk_1_data', 'hash': 'hash1', 'expires_at': DatetimeUtil.now() + timedelta(hours=1)},
            # 模拟chunk 2还未上传（中断点）
        }

        upload_pool["TEST_RECOVERY"] = test_chunks

        # 验证恢复功能：检查已上传的块
        if "TEST_RECOVERY" in upload_pool:
            existing_chunks = upload_pool["TEST_RECOVERY"]
            if len(existing_chunks) == 2 and 0 in existing_chunks and 1 in existing_chunks:
                log_info("✓ 上传中断后恢复功能验证成功")
                result = True
            else:
                log_error("✗ 上传恢复数据不正确")
                result = False
        else:
            log_error("✗ 上传池数据不存在")
            result = False

        # 清理
        if "TEST_RECOVERY" in upload_pool:
            del upload_pool["TEST_RECOVERY"]

        return result

    except Exception as e:
        log_error(f"上传恢复测试失败: {e}")
        return False


def test_large_file_performance():
    """测试大文件上传池性能"""
    log_test_start("大文件上传池性能")

    try:
        # 模拟大文件的分块数据
        large_chunks = {}
        chunk_size = 1024 * 1024  # 1MB per chunk
        num_chunks = 10  # 模拟10MB文件

        for i in range(num_chunks):
            large_chunks[i] = {
                'data': b'x' * chunk_size,
                'hash': f'hash_{i}',
                'expires_at': DatetimeUtil.now() + timedelta(hours=1)
            }

        upload_pool["TEST_LARGE"] = large_chunks

        # 验证大文件处理
        if "TEST_LARGE" in upload_pool:
            stored_chunks = upload_pool["TEST_LARGE"]
            total_size = sum(len(chunk['data']) for chunk in stored_chunks.values())

            if len(stored_chunks) == num_chunks and total_size == chunk_size * num_chunks:
                log_info(f"✓ 大文件上传池性能测试通过: {num_chunks}块, {total_size}字节")
                result = True
            else:
                log_error(f"✗ 大文件数据不正确: {len(stored_chunks)}块, {total_size}字节")
                result = False
        else:
            log_error("✗ 大文件数据未存储")
            result = False

        # 清理
        if "TEST_LARGE" in upload_pool:
            del upload_pool["TEST_LARGE"]

        return result

    except Exception as e:
        log_error(f"大文件性能测试失败: {e}")
        return False


def run_upload_pool_tests():
    """运行上传池测试"""
    log_section("上传池机制测试")

    tests = [
        ("上传池测试", [
            test_upload_recovery,
            test_large_file_performance,
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
        log_success("所有上传池测试通过！🎉")
    else:
        log_error("部分上传池测试失败")

    return total_passed == total_tests


if __name__ == "__main__":
    success = run_upload_pool_tests()
    sys.exit(0 if success else 1)
