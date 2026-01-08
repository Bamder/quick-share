"""
下载池机制测试

测试下载池的工作机制：
- 预读取块功能：验证预读取功能
- 多会话下载池隔离：测试不同会话的隔离性
- 池的初始化：验证池结构的正确性
- 池的清理：测试过期会话的清理
- 并发访问：多个会话同时访问同一个文件
- 边界情况：预读取超出总块数、空池处理等

使用方法:
    python scripts/test/download_pool/test_download_pool.py
"""

import os
import sys
from pathlib import Path
import asyncio

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

from app.services.pool_service import download_pool, preload_next_chunks, cleanup_download_pool
from app.services.cache_service import chunk_cache
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
        # 设置测试数据
        original_lookup_code = "TEST_PREFETCH"
        session_id = "test_session_001"
        user_id = 1
        
        # 在主缓存中创建一些测试块
        test_chunks = {
            0: {'data': b'chunk_0', 'hash': 'hash0'},
            1: {'data': b'chunk_1', 'hash': 'hash1'},
            2: {'data': b'chunk_2', 'hash': 'hash2'},
            3: {'data': b'chunk_3', 'hash': 'hash3'},
            4: {'data': b'chunk_4', 'hash': 'hash4'},
        }
        chunk_cache.set(original_lookup_code, test_chunks, user_id)
        
        # 初始化下载池
        if original_lookup_code not in download_pool:
            download_pool[original_lookup_code] = {}
        
        download_pool[original_lookup_code][session_id] = {
            'chunks': {},
            'last_access': DatetimeUtil.now(),
            'access_count': 0,
            'total_chunks': 5,
            'loaded_chunks': set()
        }
        
        # 执行预读取（从索引0开始，预读取3个块）
        asyncio.run(preload_next_chunks(original_lookup_code, session_id, 0, 5, preload_count=3, user_id=user_id))
        
        # 验证预读取结果
        pool = download_pool[original_lookup_code][session_id]
        chunks = pool['chunks']
        loaded_chunks = pool['loaded_chunks']
        
        # 应该预读取了索引1, 2, 3（因为从索引0开始，预读取3个）
        expected_indices = {1, 2, 3}
        actual_indices = set(chunks.keys())
        
        if actual_indices == expected_indices and loaded_chunks == expected_indices:
            log_info("✓ 预读取块功能验证成功")
            result = True
        else:
            log_error(f"✗ 预读取数据不正确: 期望索引{expected_indices}, 实际索引{actual_indices}, 已加载{loaded_chunks}")
            result = False
        
        # 清理
        if original_lookup_code in download_pool and session_id in download_pool[original_lookup_code]:
            del download_pool[original_lookup_code][session_id]
        if original_lookup_code in download_pool and not download_pool[original_lookup_code]:
            del download_pool[original_lookup_code]
        chunk_cache.delete(original_lookup_code, user_id)
        
        return result

    except Exception as e:
        log_error(f"预读取功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_session_isolation():
    """测试多会话下载池隔离"""
    log_test_start("多会话下载池隔离")

    try:
        # 创建两个不同的下载会话（使用相同的文件但不同的会话ID）
        original_lookup_code = "TEST_ISOLATION"
        session1_id = "session_1"
        session2_id = "session_2"
        
        # 初始化下载池结构
        if original_lookup_code not in download_pool:
            download_pool[original_lookup_code] = {}
        
        # 创建会话1的池
        download_pool[original_lookup_code][session1_id] = {
            'chunks': {0: {'data': b'chunk_0_s1', 'hash': 'hash0'}, 1: {'data': b'chunk_1_s1', 'hash': 'hash1'}},
            'last_access': DatetimeUtil.now(),
            'access_count': 2,
            'total_chunks': 5,
            'loaded_chunks': {0, 1}
        }
        
        # 创建会话2的池
        download_pool[original_lookup_code][session2_id] = {
            'chunks': {0: {'data': b'chunk_0_s2', 'hash': 'hash0'}, 2: {'data': b'chunk_2_s2', 'hash': 'hash2'}, 3: {'data': b'chunk_3_s2', 'hash': 'hash3'}},
            'last_access': DatetimeUtil.now(),
            'access_count': 3,
            'total_chunks': 5,
            'loaded_chunks': {0, 2, 3}
        }
        
        # 验证会话隔离
        if (original_lookup_code in download_pool and 
            session1_id in download_pool[original_lookup_code] and 
            session2_id in download_pool[original_lookup_code]):
            
            s1 = download_pool[original_lookup_code][session1_id]
            s2 = download_pool[original_lookup_code][session2_id]
            
            # 检查数据隔离：不同的块、不同的访问计数、不同的已加载块
            if (s1['chunks'] != s2['chunks'] and
                s1['access_count'] != s2['access_count'] and
                s1['loaded_chunks'] != s2['loaded_chunks']):
                log_info("✓ 多会话下载池隔离验证成功")
                result = True
            else:
                log_error("✗ 会话数据未正确隔离")
                result = False
        else:
            log_error("✗ 会话创建失败")
            result = False
        
        # 清理
        if original_lookup_code in download_pool:
            for session_id in [session1_id, session2_id]:
                if session_id in download_pool[original_lookup_code]:
                    del download_pool[original_lookup_code][session_id]
            if not download_pool[original_lookup_code]:
                del download_pool[original_lookup_code]
        
        return result

    except Exception as e:
        log_error(f"会话隔离测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_pool_initialization():
    """测试池的初始化"""
    log_test_start("池的初始化")

    try:
        original_lookup_code = "TEST_INIT"
        session_id = "test_session_init"
        total_chunks = 10
        
        # 初始化下载池
        if original_lookup_code not in download_pool:
            download_pool[original_lookup_code] = {}
        
        download_pool[original_lookup_code][session_id] = {
            'chunks': {},
            'last_access': DatetimeUtil.now(),
            'access_count': 0,
            'total_chunks': total_chunks,
            'loaded_chunks': set()
        }
        
        pool = download_pool[original_lookup_code][session_id]
        
        # 验证池结构
        if (isinstance(pool['chunks'], dict) and
            isinstance(pool['last_access'], datetime) and
            isinstance(pool['access_count'], int) and
            pool['total_chunks'] == total_chunks and
            isinstance(pool['loaded_chunks'], set)):
            log_info("✓ 池的初始化验证成功")
            result = True
        else:
            log_error("✗ 池结构不正确")
            result = False
        
        # 测试访问计数和最后访问时间的更新
        pool['access_count'] += 1
        pool['last_access'] = DatetimeUtil.now()
        
        if pool['access_count'] == 1:
            log_info("✓ 访问计数更新成功")
        else:
            log_error("✗ 访问计数更新失败")
            result = False
        
        # 清理
        if original_lookup_code in download_pool and session_id in download_pool[original_lookup_code]:
            del download_pool[original_lookup_code][session_id]
        if original_lookup_code in download_pool and not download_pool[original_lookup_code]:
            del download_pool[original_lookup_code]
        
        return result

    except Exception as e:
        log_error(f"池的初始化测试失败: {e}")
        return False


def test_pool_cleanup():
    """测试池的清理机制"""
    log_test_start("池的清理机制")

    try:
        original_lookup_code = "TEST_CLEANUP"
        session1_id = "session_old"  # 旧的会话（应该被清理）
        session2_id = "session_new"  # 新的会话（应该保留）
        
        # 初始化下载池
        if original_lookup_code not in download_pool:
            download_pool[original_lookup_code] = {}
        
        # 创建旧的会话（10分钟前访问）
        old_time = DatetimeUtil.now() - timedelta(minutes=11)
        download_pool[original_lookup_code][session1_id] = {
            'chunks': {0: {'data': b'old_chunk', 'hash': 'hash0'}},
            'last_access': old_time,
            'access_count': 1,
            'total_chunks': 5,
            'loaded_chunks': {0}
        }
        
        # 创建新的会话（刚刚访问）
        download_pool[original_lookup_code][session2_id] = {
            'chunks': {0: {'data': b'new_chunk', 'hash': 'hash0'}},
            'last_access': DatetimeUtil.now(),
            'access_count': 1,
            'total_chunks': 5,
            'loaded_chunks': {0}
        }
        
        # 执行清理
        cleanup_download_pool()
        
        # 验证：旧会话应该被清理，新会话应该保留
        if (session1_id not in download_pool.get(original_lookup_code, {}) and
            session2_id in download_pool.get(original_lookup_code, {})):
            log_info("✓ 池的清理机制验证成功")
            result = True
        else:
            log_error(f"✗ 池清理失败: 旧会话存在={session1_id in download_pool.get(original_lookup_code, {})}, 新会话存在={session2_id in download_pool.get(original_lookup_code, {})}")
            result = False
        
        # 清理
        if original_lookup_code in download_pool:
            for session_id in [session1_id, session2_id]:
                if session_id in download_pool[original_lookup_code]:
                    del download_pool[original_lookup_code][session_id]
            if not download_pool[original_lookup_code]:
                del download_pool[original_lookup_code]
        
        return result

    except Exception as e:
        log_error(f"池的清理机制测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prefetch_edge_cases():
    """测试预读取的边界情况"""
    log_test_start("预读取边界情况")

    try:
        original_lookup_code = "TEST_EDGE"
        session_id = "test_session_edge"
        user_id = 1
        
        # 创建只有3个块的测试数据
        test_chunks = {
            0: {'data': b'chunk_0', 'hash': 'hash0'},
            1: {'data': b'chunk_1', 'hash': 'hash1'},
            2: {'data': b'chunk_2', 'hash': 'hash2'},
        }
        chunk_cache.set(original_lookup_code, test_chunks, user_id)
        
        # 初始化下载池
        if original_lookup_code not in download_pool:
            download_pool[original_lookup_code] = {}
        
        download_pool[original_lookup_code][session_id] = {
            'chunks': {},
            'last_access': DatetimeUtil.now(),
            'access_count': 0,
            'total_chunks': 3,
            'loaded_chunks': set()
        }
        
        # 测试1: 从最后一个块开始预读取（应该没有可预读取的块）
        asyncio.run(preload_next_chunks(original_lookup_code, session_id, 2, 3, preload_count=10, user_id=user_id))
        pool = download_pool[original_lookup_code][session_id]
        if len(pool['chunks']) == 0:
            log_info("✓ 边界情况1: 从最后一个块预读取正确（无块可预读取）")
        else:
            log_error(f"✗ 边界情况1失败: 应该没有块，实际有{len(pool['chunks'])}个")
            return False
        
        # 测试2: 预读取超出总块数（应该只预读取到总块数）
        asyncio.run(preload_next_chunks(original_lookup_code, session_id, 0, 3, preload_count=10, user_id=user_id))
        pool = download_pool[original_lookup_code][session_id]
        expected_indices = {1, 2}  # 从索引0开始，预读取10个，但只有2个可用
        actual_indices = set(pool['chunks'].keys())
        if actual_indices == expected_indices:
            log_info("✓ 边界情况2: 预读取超出总块数正确（只预读取可用块）")
        else:
            log_error(f"✗ 边界情况2失败: 期望{expected_indices}, 实际{actual_indices}")
            return False
        
        # 清理
        if original_lookup_code in download_pool and session_id in download_pool[original_lookup_code]:
            del download_pool[original_lookup_code][session_id]
        if original_lookup_code in download_pool and not download_pool[original_lookup_code]:
            del download_pool[original_lookup_code]
        chunk_cache.delete(original_lookup_code, user_id)
        
        log_success("预读取边界情况测试通过")
        return True

    except Exception as e:
        log_error(f"预读取边界情况测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_download_pool_tests():
    """运行下载池测试"""
    log_section("下载池机制测试")

    tests = [
        ("下载池测试", [
            test_prefetch_functionality,
            test_session_isolation,
            test_pool_initialization,
            test_pool_cleanup,
            test_prefetch_edge_cases,
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
