from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from app.models.file import File
from app.models.pickup_code import PickupCode
from app.services.cache_service import chunk_cache, file_info_cache
from app.services.pool_service import upload_pool
from app.services.mapping_service import get_identifier_code
from app.utils.pickup_code import DatetimeUtil
import logging

logger = logging.getLogger(__name__)


class FileReuseService:
    """文件复用服务 - 处理文件存在性检查和复用逻辑"""

    @staticmethod
    def check_file_exists(
        hash_value: Optional[str],
        original_name: str,
        size: int,
        uploader_id: Optional[int],
        db: Session
    ) -> Tuple[Optional[File], bool]:
        """
        检查文件是否已存在

        Args:
            hash_value: 文件明文哈希值（前端SHA-256，可选）
            original_name: 原始文件名
            size: 文件大小
            uploader_id: 上传者ID
            db: 数据库会话

        Returns:
            (existing_file, file_unchanged) 元组
            - existing_file: 存在的文件记录，如果没有则为None
            - file_unchanged: 如果找到的文件哈希匹配且用户匹配，则为True
        """
        file_unchanged = False

        # 1. 优先通过哈希查找（如果提供了哈希）
        if hash_value:
            from app.utils.dedupe import derive_dedupe_fingerprint
            dedupe_fingerprint = derive_dedupe_fingerprint(
                user_id=uploader_id,
                plaintext_file_hash=hash_value
            )

            existing_file = db.query(File).filter(
                File.hash == dedupe_fingerprint,
                File.uploader_id == uploader_id
            ).first()

            if existing_file:
                file_unchanged = True
                logger.info(
                    f"通过去重指纹找到已存在的文件: file_id={existing_file.id}, "
                    f"fingerprint={existing_file.hash[:16]}..., uploader_id={existing_file.uploader_id}"
                )
                return existing_file, file_unchanged

        # 2. 通过文件名+大小+用户ID查找（降级策略）
        if uploader_id is not None:
            existing_file = db.query(File).filter(
                File.original_name == original_name,
                File.size == size,
                File.uploader_id == uploader_id
            ).first()
        else:
            # 匿名用户：只使用文件名+大小查找
            existing_file = db.query(File).filter(
                File.original_name == original_name,
                File.size == size
            ).first()

        if existing_file:
            # 检查文件是否已被废弃
            if existing_file.is_invalidated:
                logger.info(f"找到的文件已被废弃 (file_id={existing_file.id})，不允许复用，创建新文件记录")
                existing_file = None  # 重置，不复用已废弃的文件
            else:
                # 文件存在且未被废弃，允许复用
                file_unchanged = True
                logger.info(f"通过文件名+大小+用户ID找到已存在的文件: file_id={existing_file.id}, name={original_name}, size={size}, uploader_id={uploader_id}")

        return existing_file, file_unchanged

    @staticmethod
    def check_file_reuse_eligibility(
        existing_file: File,
        uploader_id: Optional[int],
        db: Session
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        检查文件是否可以复用

        Args:
            existing_file: 存在的文件记录
            uploader_id: 当前上传者ID
            db: 数据库会话

        Returns:
            (can_reuse, original_lookup_code, file_info) 元组
            - can_reuse: 是否可以复用
            - original_lookup_code: 原始取件码
            - file_info: 文件信息字典
        """
        # 检查文件是否已被废弃
        if existing_file.is_invalidated:
            logger.info(f"找到的文件已被废弃 (file_id={existing_file.id})，不允许复用")
            return False, None, {}

        # 查询该文件关联的所有活跃取件码
        all_pickup_codes = db.query(PickupCode.code).filter(
            PickupCode.file_id == existing_file.id,
            PickupCode.status.in_(["waiting", "transferring"])
        ).all()

        original_lookup_code = None

        # 找到第一个有缓存的取件码，并通过标识码查找缓存
        for pickup_code_row in all_pickup_codes:
            test_lookup_code = pickup_code_row.code
            # 获取标识码（缓存是用标识码存储的）
            test_identifier_code = get_identifier_code(test_lookup_code, db, "check_existing_file")

            # 先检查临时池（使用标识码）
            if test_identifier_code in upload_pool and upload_pool[test_identifier_code]:
                original_lookup_code = test_lookup_code
                logger.info(f"✓ 在临时池找到缓存: lookup_code={test_lookup_code}, identifier_code={test_identifier_code}")
                break

            # 再检查主缓存（使用标识码）
            if uploader_id is not None and chunk_cache.exists(test_identifier_code, uploader_id):
                original_lookup_code = test_lookup_code
                logger.info(f"✓ 在主缓存找到缓存: lookup_code={test_lookup_code}, identifier_code={test_identifier_code}")
                break
            elif uploader_id is None and chunk_cache.exists(test_identifier_code, None):
                original_lookup_code = test_lookup_code
                logger.info(f"✓ 在主缓存找到缓存（匿名用户）: lookup_code={test_lookup_code}, identifier_code={test_identifier_code}")
                break

        # 如果没找到有缓存的取件码，使用最早的活跃取件码
        if not original_lookup_code and all_pickup_codes:
            earliest_pickup_code = db.query(PickupCode.code).filter(
                PickupCode.file_id == existing_file.id,
                PickupCode.status.in_(["waiting", "transferring"])
            ).order_by(PickupCode.created_at.asc()).first()

            if earliest_pickup_code:
                original_lookup_code = earliest_pickup_code.code
                logger.info(f"未找到有缓存的取件码，使用最早的活跃取件码: lookup_code={original_lookup_code}")

        # 检查是否所有取件码都已过期
        from sqlalchemy import exists
        all_expired = not db.query(exists().where(
            PickupCode.file_id == existing_file.id,
            PickupCode.status != "expired"
        )).scalar()

        # 无论取件码是否过期，都应该检查缓存，如果存在就提示用户是否可以复用
        has_file_info = False
        has_chunks = False
        chunks_expired = True

        # 使用标识码查找文件缓存
        identifier_code = None
        if original_lookup_code:
            try:
                identifier_code = get_identifier_code(original_lookup_code, db, "reuse_file_check")
                if identifier_code:
                    logger.info(f"从映射服务获取标识码: original_lookup_code={original_lookup_code} -> identifier_code={identifier_code}")

                # 如果映射服务没有，尝试从文件信息缓存获取
                if not identifier_code:
                    if uploader_id is not None and file_info_cache.exists(original_lookup_code, uploader_id):
                        fi = file_info_cache.get(original_lookup_code, uploader_id) or {}
                    elif uploader_id is None and file_info_cache.exists(original_lookup_code, None):
                        fi = file_info_cache.get(original_lookup_code, None) or {}
                    else:
                        fi = {}

                    if fi:
                        has_file_info = True
                        chunks_expired = False  # 假设有文件信息就有块

            except Exception as e:
                logger.warning(f"检查文件缓存时出错: {e}")

        file_info = {
            "has_file_info": has_file_info,
            "has_chunks": has_chunks,
            "chunks_expired": chunks_expired,
            "all_expired": all_expired,
            "identifier_code": identifier_code
        }

        can_reuse = bool(original_lookup_code and (has_file_info or not chunks_expired))
        return can_reuse, original_lookup_code, file_info

    @staticmethod
    def check_active_pickup_code(existing_file: File, db: Session) -> Tuple[bool, Optional[PickupCode]]:
        """
        检查文件是否有未过期的活跃取件码

        Args:
            existing_file: 存在的文件记录
            db: 数据库会话

        Returns:
            (has_active, pickup_code) 元组
            - has_active: 是否有活跃的取件码
            - pickup_code: 活跃的取件码对象，如果没有则为None
        """
        now = DatetimeUtil.now()

        # 查找该文件关联的未过期且未完成的取件码
        existing_pickup_codes = db.query(PickupCode).filter(
            PickupCode.file_id == existing_file.id,
            PickupCode.status.in_(["waiting", "transferring"])  # 只查找等待中或传输中的
        ).all()

        # 在Python中检查过期时间，确保时区一致性
        existing_pickup_code = None
        for code in existing_pickup_codes:
            if code.expire_at:
                code_expire_at = DatetimeUtil.ensure_aware(code.expire_at)
                if code_expire_at > now:
                    existing_pickup_code = code
                    break

        # 如果没有找到未过期的，按创建时间倒序取最新的
        if not existing_pickup_code and existing_pickup_codes:
            existing_pickup_code = existing_pickup_codes[0]

        # 检查并更新过期状态
        if existing_pickup_code:
            from app.utils.pickup_code import check_and_update_expired_pickup_code
            check_and_update_expired_pickup_code(existing_pickup_code, db)
            db.refresh(existing_pickup_code)

        has_active = existing_pickup_code and existing_pickup_code.status in ["waiting", "transferring"] and \
                    existing_pickup_code.expire_at and DatetimeUtil.ensure_aware(existing_pickup_code.expire_at) > now

        return has_active, existing_pickup_code
