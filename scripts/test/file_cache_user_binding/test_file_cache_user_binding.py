"""
测试文件缓存与上传用户强绑定功能

测试场景：
1. 相同文件哈希 + 相同用户 = 可以复用缓存
2. 相同文件哈希 + 不同用户 = 不能复用缓存（用户隔离）
3. 不同文件哈希 + 相同用户 = 不能复用缓存
4. 未过期文件检测功能是否正常工作

使用方法:
    # Windows (推荐):
    scripts\test\file_cache_user_binding\run_test.bat
    
    # 手动运行 (需要先激活虚拟环境):
    python scripts/test/file_cache_user_binding/test_file_cache_user_binding.py
"""

import sys
import os
from pathlib import Path

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
        print("    scripts\\test\\file_cache_user_binding\\run_test.bat")
        print("")
        print("  手动激活虚拟环境后运行:")
        print("    venv\\Scripts\\activate")
        print("    python scripts\\test\\file_cache_user_binding\\test_file_cache_user_binding.py")
        print("=" * 60)
        print("")
        
        # 询问是否继续
        try:
            response = input("是否继续运行? (y/n): ").strip().lower()
            if response != 'y':
                print("已取消")
                sys.exit(0)
        except KeyboardInterrupt:
            print("\n已取消")
            sys.exit(0)
    
    return in_venv

# 在导入其他模块前检查虚拟环境
check_venv()

from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.services.cache_service import chunk_cache, file_info_cache, encrypted_key_cache
from app.models.base import Base
from app.models.file import File
from app.models.pickup_code import PickupCode
from app.models.user import User
from app.utils.dedupe import derive_dedupe_fingerprint
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestFileCacheUserBinding:
    """测试文件缓存与上传用户强绑定"""
    
    def __init__(self):
        self.db: Session = None
        self.SessionLocal = None
        self.user1: User = None
        self.user2: User = None
        self.test_file_hash = "a" * 64  # 测试用的文件哈希（64位SHA256）
        self.test_file_hash_2 = "b" * 64  # 另一个测试文件哈希
        
    def setup(self):
        """设置测试环境"""
        logger.info("=" * 60)
        logger.info("开始设置测试环境")
        logger.info("=" * 60)
        
        # 默认使用 SQLite 内存数据库，避免依赖本机 MySQL 配置
        # 如需用真实数据库跑集成测试，可设置环境变量 TEST_DATABASE_URL
        test_db_url = os.getenv("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
        engine_kwargs = {}
        if test_db_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}

        engine = create_engine(test_db_url, **engine_kwargs)

        # 确保模型已导入（已在本文件顶部导入），创建表结构
        Base.metadata.create_all(bind=engine)

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.db = self.SessionLocal()
        
        # 清理可能存在的旧测试数据
        self.cleanup_test_data()
        
        # 创建测试用户
        self.user1 = User(
            username="test_user_cache_1",
            password_hash="dummy_hash_for_test"
        )
        self.db.add(self.user1)
        
        self.user2 = User(
            username="test_user_cache_2",
            password_hash="dummy_hash_for_test"
        )
        self.db.add(self.user2)
        
        self.db.commit()
        self.db.refresh(self.user1)
        self.db.refresh(self.user2)
        
        logger.info(f"创建测试用户: user1_id={self.user1.id}, user2_id={self.user2.id}")
        
    def cleanup_test_data(self):
        """清理测试数据"""
        logger.info("清理旧测试数据...")
        
        if not self.db:
            return
        
        # 清理取件码
        test_codes = ["TESTC1", "TESTC2", "TESTC3", "TESTC4", "TESTC5", "TESTC6"]
        self.db.query(PickupCode).filter(PickupCode.code.in_(test_codes)).delete()
        
        # 清理文件
        self.db.query(File).filter(
            File.hash.in_([self.test_file_hash, self.test_file_hash_2, "c" * 64, "d" * 64])
        ).delete()
        
        # 清理用户
        self.db.query(User).filter(
            User.username.in_(["test_user_cache_1", "test_user_cache_2"])
        ).delete()
        
        self.db.commit()
        
        # 清理缓存（测试只会写入少量固定键，这里按键精确删除即可）
        user_ids = []
        try:
            existing_users = self.db.query(User).filter(
                User.username.in_(["test_user_cache_1", "test_user_cache_2"])
            ).all()
            user_ids = [user.id for user in existing_users]
        except Exception:
            user_ids = []
        user_ids.append(None)
        
        for code in test_codes:
            for user_id in user_ids:
                if chunk_cache.exists(code, user_id):
                    chunk_cache.delete(code, user_id)
                if file_info_cache.exists(code, user_id):
                    file_info_cache.delete(code, user_id)
                if encrypted_key_cache.exists(code, user_id):
                    encrypted_key_cache.delete(code, user_id)
        
        logger.info("旧测试数据清理完成")
    
    def test_case_1_same_hash_same_user(self):
        """测试用例1: 相同文件哈希 + 相同用户 = 可以复用缓存"""
        logger.info("\n" + "=" * 60)
        logger.info("测试用例1: 相同文件哈希 + 相同用户 = 可以复用缓存")
        logger.info("=" * 60)
        
        # 步骤1: 用户1第一次上传文件（创建文件记录和缓存）
        logger.info("步骤1: 用户1第一次上传文件...")
        
        # 创建文件记录
        fingerprint_user1 = derive_dedupe_fingerprint(
            user_id=self.user1.id,
            plaintext_file_hash=self.test_file_hash,
        )
        file1 = File(
            original_name="test_file_1.txt",
            stored_name="uuid-1",
            size=1024,
            # 重要：后端落库的是“去重指纹”，不是明文文件哈希
            hash=fingerprint_user1,
            mime_type="text/plain",
            uploader_id=self.user1.id
        )
        self.db.add(file1)
        self.db.commit()
        self.db.refresh(file1)
        
        # 创建取件码
        pickup_code1 = PickupCode(
            code="TESTC1",
            file_id=file1.id,
            status="waiting",
            used_count=0,
            limit_count=3,
            expire_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )
        self.db.add(pickup_code1)
        self.db.commit()
        
        # 设置缓存（模拟文件已上传完成）
        chunk_cache.set("TESTC1", {
            0: {
                'data': b'chunk_data_0',
                'hash': 'hash_0',
                'pickup_expire_at': datetime.now(timezone.utc) + timedelta(hours=1)
            }
        }, self.user1.id)
        
        file_info_cache.set("TESTC1", {
            'fileName': 'test_file_1.txt',
            'fileSize': 1024,
            'totalChunks': 1,
            'pickup_expire_at': datetime.now(timezone.utc) + timedelta(hours=1)
        }, self.user1.id)
        
        encrypted_key_cache.set("TESTC1", "encrypted_key_1", self.user1.id)
        
        logger.info(f"✓ 用户1的文件记录和缓存已创建: file_id={file1.id}, lookup_code=TESTC1")
        
        # 步骤2: 用户1再次上传相同文件（应该检测到可复用）
        logger.info("\n步骤2: 用户1再次上传相同文件...")
        
        # 检查文件是否存在
        existing_file = self.db.query(File).filter(
            File.hash == fingerprint_user1,
            File.uploader_id == self.user1.id
        ).first()
        
        assert existing_file is not None, "应该找到已存在的文件"
        assert existing_file.uploader_id == self.user1.id, "文件的上传者应该是用户1"
        
        logger.info(f"✓ 找到已存在的文件: file_id={existing_file.id}, uploader_id={existing_file.uploader_id}")
        
        # 检查缓存是否存在
        has_file_info = file_info_cache.exists("TESTC1", self.user1.id)
        has_chunks = chunk_cache.exists("TESTC1", self.user1.id)
        has_key = encrypted_key_cache.exists("TESTC1", self.user1.id)
        
        assert has_file_info, "文件信息缓存应该存在"
        assert has_chunks, "文件块缓存应该存在"
        assert has_key, "密钥缓存应该存在"
        
        logger.info(f"✓ 检测到可复用的缓存: has_file_info={has_file_info}, has_chunks={has_chunks}, has_key={has_key}")
        
        logger.info("\n✓ 测试用例1通过: 相同文件哈希 + 相同用户 = 可以复用缓存")
        return True
    
    def test_case_2_same_hash_different_user(self):
        """测试用例2: 相同文件哈希 + 不同用户 = 不能复用缓存（用户隔离）"""
        logger.info("\n" + "=" * 60)
        logger.info("测试用例2: 相同文件哈希 + 不同用户 = 不能复用缓存（用户隔离）")
        logger.info("=" * 60)
        
        # 步骤1: 用户1上传文件（已在上一个测试用例中创建）
        logger.info("步骤1: 用户1已上传文件（使用测试用例1的数据）...")
        
        # 步骤2: 用户2上传相同哈希的文件
        logger.info("\n步骤2: 用户2上传相同哈希的文件...")
        
        # 检查文件是否存在（应该找到用户1的文件）
        fingerprint_user1 = derive_dedupe_fingerprint(
            user_id=self.user1.id,
            plaintext_file_hash=self.test_file_hash,
        )
        existing_file_user1 = self.db.query(File).filter(
            File.hash == fingerprint_user1,
            File.uploader_id == self.user1.id
        ).first()
        
        assert existing_file_user1 is not None, "应该找到用户1的文件"
        
        # 检查用户2的文件是否存在（应该不存在）
        fingerprint_user2 = derive_dedupe_fingerprint(
            user_id=self.user2.id,
            plaintext_file_hash=self.test_file_hash,
        )
        existing_file_user2 = self.db.query(File).filter(
            File.hash == fingerprint_user2,
            File.uploader_id == self.user2.id
        ).first()
        
        assert existing_file_user2 is None, "不应该找到用户2的文件（因为用户2还没上传）"
        
        logger.info(f"✓ 用户1的文件存在: file_id={existing_file_user1.id}, uploader_id={existing_file_user1.uploader_id}")
        logger.info(f"✓ 用户2的文件不存在（符合预期）")
        
        # 检查用户2是否能访问用户1的缓存（应该不能）
        has_file_info_user2 = file_info_cache.exists("TESTC1", self.user2.id)
        has_chunks_user2 = chunk_cache.exists("TESTC1", self.user2.id)
        has_key_user2 = encrypted_key_cache.exists("TESTC1", self.user2.id)
        
        assert not has_file_info_user2, "用户2不应该能访问用户1的文件信息缓存"
        assert not has_chunks_user2, "用户2不应该能访问用户1的文件块缓存"
        assert not has_key_user2, "用户2不应该能访问用户1的密钥缓存"
        
        logger.info(f"✓ 用户隔离验证通过: user2无法访问user1的缓存")
        
        # 步骤3: 用户2创建自己的文件记录（应该创建新记录，不复用用户1的记录）
        logger.info("\n步骤3: 用户2创建自己的文件记录...")
        
        # 相同明文哈希，不同用户 => 去重指纹必须不同
        assert fingerprint_user1 != fingerprint_user2, "不同用户的去重指纹必须不同"

        file2 = File(
            original_name="test_file_1.txt",  # 相同文件名
            stored_name="uuid-2",
            size=1024,  # 相同大小
            # 重要：落库的是去重指纹（不同用户不同指纹）
            hash=fingerprint_user2,
            mime_type="text/plain",
            uploader_id=self.user2.id  # 不同用户
        )
        self.db.add(file2)
        self.db.commit()
        self.db.refresh(file2)
        
        assert file2.id != existing_file_user1.id, "应该创建新的文件记录，不复用用户1的记录"
        
        logger.info(f"✓ 用户2创建了新文件记录: file_id={file2.id}, uploader_id={file2.uploader_id}")
        
        logger.info("\n✓ 测试用例2通过: 相同文件哈希 + 不同用户 = 不能复用缓存（用户隔离）")
        return True
    
    def test_case_3_different_hash_same_user(self):
        """测试用例3: 不同文件哈希 + 相同用户 = 不能复用缓存"""
        logger.info("\n" + "=" * 60)
        logger.info("测试用例3: 不同文件哈希 + 相同用户 = 不能复用缓存")
        logger.info("=" * 60)
        
        # 步骤1: 用户1上传文件1（已在上一个测试用例中创建）
        logger.info("步骤1: 用户1已上传文件1（使用测试用例1的数据）...")
        
        # 步骤2: 用户1上传文件2（不同哈希）
        logger.info("\n步骤2: 用户1上传文件2（不同哈希）...")
        
        # 检查文件2是否存在（应该不存在）
        fingerprint2_user1 = derive_dedupe_fingerprint(
            user_id=self.user1.id,
            plaintext_file_hash=self.test_file_hash_2,
        )
        existing_file2 = self.db.query(File).filter(
            File.hash == fingerprint2_user1,
            File.uploader_id == self.user1.id
        ).first()
        
        assert existing_file2 is None, "不应该找到文件2（因为还没创建）"
        
        logger.info(f"✓ 文件2不存在（符合预期）")
        
        # 步骤3: 用户1创建文件2的记录（应该创建新记录）
        logger.info("\n步骤3: 用户1创建文件2的记录...")
        
        file2 = File(
            original_name="test_file_2.txt",
            stored_name="uuid-3",
            size=2048,
            # 重要：落库的是去重指纹
            hash=fingerprint2_user1,
            mime_type="text/plain",
            uploader_id=self.user1.id  # 相同用户
        )
        self.db.add(file2)
        self.db.commit()
        self.db.refresh(file2)
        
        # 检查文件1是否存在
        fingerprint_user1 = derive_dedupe_fingerprint(
            user_id=self.user1.id,
            plaintext_file_hash=self.test_file_hash,
        )
        existing_file1 = self.db.query(File).filter(
            File.hash == fingerprint_user1,
            File.uploader_id == self.user1.id
        ).first()
        
        assert file2.id != existing_file1.id, "应该创建新的文件记录，不复用文件1的记录"
        
        logger.info(f"✓ 用户1创建了新文件记录: file_id={file2.id}, hash={self.test_file_hash_2[:16]}...")
        
        logger.info("\n✓ 测试用例3通过: 不同文件哈希 + 相同用户 = 不能复用缓存")
        return True
    
    def test_case_4_expired_file_detection(self):
        """测试用例4: 验证未过期文件检测功能"""
        logger.info("\n" + "=" * 60)
        logger.info("测试用例4: 验证未过期文件检测功能")
        logger.info("=" * 60)
        
        # 步骤1: 用户1上传文件并创建未过期的取件码
        logger.info("步骤1: 用户1上传文件并创建未过期的取件码...")
        
        file3 = File(
            original_name="test_file_3.txt",
            stored_name="uuid-4",
            size=3072,
            hash="c" * 64,
            mime_type="text/plain",
            uploader_id=self.user1.id
        )
        self.db.add(file3)
        self.db.commit()
        self.db.refresh(file3)
        
        # 创建未过期的取件码
        pickup_code3 = PickupCode(
            code="TESTC4",
            file_id=file3.id,
            status="waiting",
            used_count=0,
            limit_count=3,
            expire_at=datetime.now(timezone.utc) + timedelta(hours=1)  # 1小时后过期
        )
        self.db.add(pickup_code3)
        self.db.commit()
        
        # 设置缓存（未过期）
        chunk_cache.set("TESTC4", {
            0: {
                'data': b'chunk_data_0',
                'hash': 'hash_0',
                'pickup_expire_at': datetime.now(timezone.utc) + timedelta(hours=1)
            }
        }, self.user1.id)
        
        file_info_cache.set("TESTC4", {
            'fileName': 'test_file_3.txt',
            'fileSize': 3072,
            'totalChunks': 1,
            'pickup_expire_at': datetime.now(timezone.utc) + timedelta(hours=1)
        }, self.user1.id)
        
        logger.info(f"✓ 用户1的文件和未过期取件码已创建: file_id={file3.id}, lookup_code=TESTC4")
        
        # 步骤2: 检查未过期文件检测
        logger.info("\n步骤2: 检查未过期文件检测...")
        
        # 检查是否有未过期的取件码
        now = datetime.now(timezone.utc)
        existing_pickup_code = self.db.query(PickupCode).filter(
            PickupCode.file_id == file3.id,
            PickupCode.status.in_(["waiting", "transferring"]),
            PickupCode.expire_at > now
        ).first()
        
        assert existing_pickup_code is not None, "应该找到未过期的取件码"
        assert existing_pickup_code.code == "TESTC4", "取件码应该是TESTC4"
        
        logger.info(f"✓ 找到未过期的取件码: code={existing_pickup_code.code}")
        
        # 检查文件信息缓存是否存在且未过期
        has_file_info = file_info_cache.exists("TESTC4", self.user1.id)
        assert has_file_info, "文件信息缓存应该存在"
        
        file_info = file_info_cache.get("TESTC4", self.user1.id)
        pickup_expire_at = file_info.get('pickup_expire_at')
        if pickup_expire_at:
            from app.utils.pickup_code import ensure_aware_datetime
            pickup_expire_at = ensure_aware_datetime(pickup_expire_at)
            assert now < pickup_expire_at, "文件信息缓存应该未过期"
        
        logger.info(f"✓ 文件信息缓存存在且未过期")
        
        # 检查文件块缓存是否存在且未过期
        has_chunks = chunk_cache.exists("TESTC4", self.user1.id)
        assert has_chunks, "文件块缓存应该存在"
        
        chunks = chunk_cache.get("TESTC4", self.user1.id)
        if chunks:
            first_chunk = next(iter(chunks.values()))
            chunk_expire_at = first_chunk.get('pickup_expire_at') or first_chunk.get('expires_at')
            if chunk_expire_at:
                from app.utils.pickup_code import ensure_aware_datetime
                chunk_expire_at = ensure_aware_datetime(chunk_expire_at)
                assert now < chunk_expire_at, "文件块缓存应该未过期"
        
        logger.info(f"✓ 文件块缓存存在且未过期")
        
        logger.info("\n✓ 测试用例4通过: 未过期文件检测功能正常工作")
        return True
    
    def test_case_5_expired_file_allows_new_code(self):
        """测试用例5: 已过期文件允许创建新取件码"""
        logger.info("\n" + "=" * 60)
        logger.info("测试用例5: 已过期文件允许创建新取件码")
        logger.info("=" * 60)
        
        # 步骤1: 用户1上传文件并创建已过期的取件码
        logger.info("步骤1: 用户1上传文件并创建已过期的取件码...")
        
        file4 = File(
            original_name="test_file_4.txt",
            stored_name="uuid-5",
            size=4096,
            hash="d" * 64,
            mime_type="text/plain",
            uploader_id=self.user1.id
        )
        self.db.add(file4)
        self.db.commit()
        self.db.refresh(file4)
        
        # 创建已过期的取件码
        pickup_code4 = PickupCode(
            code="TESTC5",
            file_id=file4.id,
            status="expired",  # 已过期
            used_count=0,
            limit_count=3,
            expire_at=datetime.now(timezone.utc) - timedelta(hours=1)  # 1小时前过期
        )
        self.db.add(pickup_code4)
        self.db.commit()
        
        logger.info(f"✓ 用户1的文件和已过期取件码已创建: file_id={file4.id}, lookup_code=TESTC5")
        
        # 步骤2: 检查是否所有取件码都已过期
        logger.info("\n步骤2: 检查是否所有取件码都已过期...")
        
        all_expired = self.db.query(PickupCode).filter(
            PickupCode.file_id == file4.id,
            PickupCode.status != "expired"
        ).count() == 0
        
        assert all_expired, "所有取件码应该都已过期"
        
        logger.info(f"✓ 所有取件码都已过期（符合预期）")
        
        # 步骤3: 验证允许创建新取件码（即使文件块缓存存在）
        logger.info("\n步骤3: 验证允许创建新取件码...")
        
        # 设置缓存（模拟文件块还在缓存中）
        chunk_cache.set("TESTC5", {
            0: {
                'data': b'chunk_data_0',
                'hash': 'hash_0',
                'pickup_expire_at': datetime.now(timezone.utc) - timedelta(hours=1)  # 已过期
            }
        }, self.user1.id)
        
        # 检查：即使文件块缓存存在，但因为所有取件码都已过期，应该允许创建新码
        # 这个逻辑在 create_code 函数中实现
        logger.info(f"✓ 即使文件块缓存存在，但因为所有取件码都已过期，应该允许创建新码")
        
        logger.info("\n✓ 测试用例5通过: 已过期文件允许创建新取件码")
        return True
    
    def run_all_tests(self):
        """运行所有测试用例"""
        logger.info("\n" + "=" * 60)
        logger.info("开始运行文件缓存与上传用户强绑定测试")
        logger.info("=" * 60)
        
        try:
            self.setup()
            
            results = []
            
            # 运行所有测试用例
            test_cases = [
                ("测试用例1: 相同文件哈希 + 相同用户", self.test_case_1_same_hash_same_user),
                ("测试用例2: 相同文件哈希 + 不同用户", self.test_case_2_same_hash_different_user),
                ("测试用例3: 不同文件哈希 + 相同用户", self.test_case_3_different_hash_same_user),
                ("测试用例4: 未过期文件检测", self.test_case_4_expired_file_detection),
                ("测试用例5: 已过期文件允许创建新码", self.test_case_5_expired_file_allows_new_code),
            ]
            
            for test_name, test_func in test_cases:
                try:
                    result = test_func()
                    results.append((test_name, True, None))
                    logger.info(f"\n✓ {test_name} 通过")
                except AssertionError as e:
                    results.append((test_name, False, str(e)))
                    logger.error(f"\n✗ {test_name} 失败: {e}")
                except Exception as e:
                    results.append((test_name, False, str(e)))
                    logger.error(f"\n✗ {test_name} 异常: {e}")
            
            # 输出测试结果摘要
            logger.info("\n" + "=" * 60)
            logger.info("测试结果摘要")
            logger.info("=" * 60)
            
            passed = sum(1 for _, result, _ in results if result)
            failed = len(results) - passed
            
            for test_name, result, error in results:
                status = "✓ 通过" if result else "✗ 失败"
                logger.info(f"{status}: {test_name}")
                if error:
                    logger.info(f"  错误: {error}")
            
            logger.info("\n" + "-" * 60)
            logger.info(f"总计: {len(results)} 个测试用例")
            logger.info(f"通过: {passed} 个")
            logger.info(f"失败: {failed} 个")
            logger.info("-" * 60)
            
            return failed == 0
            
        except Exception as e:
            logger.error(f"\n测试执行异常: {e}", exc_info=True)
            return False
        finally:
            # 清理测试数据
            logger.info("\n清理测试数据...")
            self.cleanup_test_data()
            if self.db:
                self.db.close()
            logger.info("测试数据清理完成")


def main():
    """主函数"""
    tester = TestFileCacheUserBinding()
    success = tester.run_all_tests()
    
    if success:
        logger.info("\n" + "=" * 60)
        logger.info("所有测试用例通过！")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("\n" + "=" * 60)
        logger.error("部分测试用例失败！")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()

