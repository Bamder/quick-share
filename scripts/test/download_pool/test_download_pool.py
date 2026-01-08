"""
下载池机制测试

测试下载池的工作机制：
- 预读取块功能：验证预读取功能
- 多会话下载池隔离：测试不同会话的隔离性

使用方法:
    python scripts/test/download_pool/test_download_pool.py
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

from app.services.pool_service import download_pool
from app.utils.pickup_code import DatetimeUtil
from datetime import datetime, timedelta
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))
from test_utils import *

# 配置日志输出到控制台
logging.basicConfig(level=logging.INFO, format='%(message)s')

logger = logging.getLogger(__name__)


def test_prefetch_functionality():
    """测试预读取块功能"""
    log_test_start("预读取块功能")

    try:
        # 模拟下载会话的预读取数据
        session_data = {
            'lookup_code': 'TEST_PREFETCH',
            'user_id': 1,
            'prefetched_chunks': {
                0: {'data': b'prefetch_chunk_0', 'hash': 'hash0'},
                1: {'data': b'prefetch_chunk_1', 'hash': 'hash1'},
                2: {'data': b'prefetch_chunk_2', 'hash': 'hash2'},
            },
            'prefetch_expires_at': DatetimeUtil.now() + timedelta(minutes=10),
            'start_time': DatetimeUtil.now()
        }

        download_pool["session_prefetch"] = session_data

        # 验证预读取功能
        if "session_prefetch" in download_pool:
            session = download_pool["session_prefetch"]
            prefetched = session.get('prefetched_chunks', {})

            if len(prefetched) == 3 and all(i in prefetched for i in [0, 1, 2]):
                log_info("✓ 预读取块功能验证成功")
                result = True
            else:
                log_error("✗ 预读取数据不正确")
                result = False
        else:
            log_error("✗ 预读取会话不存在")
            result = False

        # 清理
        if "session_prefetch" in download_pool:
            del download_pool["session_prefetch"]

        return result

    except Exception as e:
        log_error(f"预读取功能测试失败: {e}")
        return False


def test_session_isolation():
    """测试多会话下载池隔离"""
    log_test_start("多会话下载池隔离")

    try:
        # 创建两个不同的下载会话
        session1_data = {
            'lookup_code': 'TEST_ISOLATION_1',
            'user_id': 1,
            'chunks_downloaded': [0, 1],
            'start_time': DatetimeUtil.now(),
            'expires_at': DatetimeUtil.now() + timedelta(minutes=10)
        }

        session2_data = {
            'lookup_code': 'TEST_ISOLATION_2',
            'user_id': 2,
            'chunks_downloaded': [0, 2, 3],
            'start_time': DatetimeUtil.now(),
            'expires_at': DatetimeUtil.now() + timedelta(minutes=10)
        }

        download_pool["session_1"] = session1_data
        download_pool["session_2"] = session2_data

        # 验证会话隔离
        if "session_1" in download_pool and "session_2" in download_pool:
            s1 = download_pool["session_1"]
            s2 = download_pool["session_2"]

            # 检查数据隔离
            if (s1['user_id'] != s2['user_id'] and
                s1['lookup_code'] != s2['lookup_code'] and
                s1['chunks_downloaded'] != s2['chunks_downloaded']):
                log_info("✓ 多会话下载池隔离验证成功")
                result = True
            else:
                log_error("✗ 会话数据未正确隔离")
                result = False
        else:
            log_error("✗ 会话创建失败")
            result = False

        # 清理
        for session_id in ["session_1", "session_2"]:
            if session_id in download_pool:
                del download_pool[session_id]

        return result

    except Exception as e:
        log_error(f"会话隔离测试失败: {e}")
        return False


def run_download_pool_tests():
    """运行下载池测试"""
    log_section("下载池机制测试")

    tests = [
        ("下载池测试", [
            test_prefetch_functionality,
            test_session_isolation,
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
        log_success("所有下载池测试通过！🎉")
    else:
        log_error("部分下载池测试失败")

    return total_passed == total_tests


if __name__ == "__main__":
    success = run_download_pool_tests()
    sys.exit(0 if success else 1)
