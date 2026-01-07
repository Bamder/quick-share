from typing import List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.file import File
from app.models.pickup_code import PickupCode
from app.services.cache_service import chunk_cache, file_info_cache, encrypted_key_cache
from app.services.mapping_service import lookup_code_mapping
from app.utils.cache import cache_manager
from app.utils.response import success_response, not_found_response
import logging

logger = logging.getLogger(__name__)


class FileManagementService:
    """文件管理服务 - 处理文件清理、废弃等管理操作"""

    @staticmethod
    async def invalidate_file(
        file_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        作废文件记录

        将文件关联的所有取件码标记为过期，并清理所有相关缓存
        注意：此操作不可逆

        Args:
            file_id: 文件ID
            db: 数据库会话

        Returns:
            响应字典
        """
        # 查询文件
        file_record = db.query(File).filter(File.id == file_id).first()
        if not file_record:
            return not_found_response(msg="文件不存在")

        # 查询该文件关联的所有取件码
        pickup_codes = db.query(PickupCode).filter(PickupCode.file_id == file_id).all()
        pickup_codes_data = [{"code": pc.code, "uploader_ip": pc.uploader_ip, "uploader_id": file_record.uploader_id} for pc in pickup_codes]

        # 将所有取件码标记为过期
        for pickup_code in pickup_codes:
            pickup_code.status = "expired"
            pickup_code.expire_at = datetime.now(timezone.utc)  # 立即过期

            # 清理该取件码的映射关系，避免后续重建失败
            lookup_code = pickup_code.code[:6]
            # 清理内存映射关系
            if lookup_code in lookup_code_mapping:
                del lookup_code_mapping[lookup_code]
                logger.debug(f"清理内存映射关系: lookup_code={lookup_code}")

            # 清理Redis映射关系
            if cache_manager.exists('lookup_mapping', lookup_code):
                cache_manager.delete('lookup_mapping', lookup_code)
                logger.debug(f"清理Redis映射关系: lookup_code={lookup_code}")

        # 将文件记录标记为已废弃
        file_record.is_invalidated = True
        file_record.updated_at = datetime.now(timezone.utc)

        db.commit()

        # 清理所有相关缓存（在事务提交后执行）
        cleanup_count = await FileManagementService._cleanup_file_caches(pickup_codes_data, db)

        logger.info(f"文件 {file_id} 已被作废，共 {len(pickup_codes)} 个取件码被标记为过期，清理了 {cleanup_count} 个缓存项")

        return success_response(
            msg="文件记录已作废",
            data={
                "fileId": file_id,
                "invalidatedCodes": len(pickup_codes),
                "cleanedCacheItems": cleanup_count
            }
        )

    @staticmethod
    async def _cleanup_file_caches(pickup_codes_data: List[Dict[str, Any]], db: Session) -> int:
        """
        清理文件相关的所有缓存

        Args:
            pickup_codes_data: 取件码数据列表 [{"code": str, "uploader_id": int}, ...]
            db: 数据库会话

        Returns:
            清理的缓存项数量
        """
        cleaned_count = 0

        # 收集所有标识码（用于清理文件块缓存和文件信息缓存）
        identifier_codes_to_clean = set()
        all_lookup_codes = set()

        for pc_data in pickup_codes_data:
            lookup_code = pc_data["code"][:6]  # 取前6位作为查找码
            all_lookup_codes.add(lookup_code)

            try:
                # 在清理缓存时，即使取件码已过期也要获取标识码
                # 因为缓存清理不依赖取件码的过期状态
                from app.models.pickup_code import PickupCode

                pickup_code = db.query(PickupCode).filter(PickupCode.code == pc_data["code"]).first()
                if pickup_code:
                    # 查找该文件最早创建的取件码作为标识码（无论状态）
                    earliest_pickup_code = db.query(PickupCode).filter(
                        PickupCode.file_id == pickup_code.file_id
                    ).order_by(PickupCode.created_at.asc()).first()

                    if earliest_pickup_code:
                        identifier_code = earliest_pickup_code.code[:6]  # 取前6位作为标识码
                        identifier_codes_to_clean.add(identifier_code)
                        logger.debug(f"获取标识码用于清理: lookup_code={lookup_code}, identifier_code={identifier_code}")
            except Exception as e:
                logger.warning(f"获取标识码失败: lookup_code={lookup_code}, error={e}")

        # 获取文件的 uploader_id（用于清理文件缓存）
        file_uploader_id = None
        if pickup_codes_data:
            file_uploader_id = pickup_codes_data[0]["uploader_id"]

        # 1. 清理文件块缓存（使用标识码和文件uploader_id）
        for identifier_code in identifier_codes_to_clean:
            if file_uploader_id is not None:
                if chunk_cache.exists(identifier_code, file_uploader_id):
                    chunk_cache.delete(identifier_code, file_uploader_id)
                    cleaned_count += 1
                    logger.debug(f"清理文件块缓存: identifier_code={identifier_code}, uploader_id={file_uploader_id}")

        # 2. 清理文件信息缓存（使用标识码和文件uploader_id）
        for identifier_code in identifier_codes_to_clean:
            if file_uploader_id is not None:
                if file_info_cache.exists(identifier_code, file_uploader_id):
                    file_info_cache.delete(identifier_code, file_uploader_id)
                    cleaned_count += 1
                    logger.debug(f"清理文件信息缓存: identifier_code={identifier_code}, uploader_id={file_uploader_id}")

        # 3. 清理加密密钥缓存（使用取件码和取件码uploader_ip）
        for pc_data in pickup_codes_data:
            lookup_code = pc_data["code"][:6]
            uploader_ip = pc_data["uploader_ip"]
            if encrypted_key_cache.exists(lookup_code, uploader_ip):
                encrypted_key_cache.delete(lookup_code, uploader_ip)
                cleaned_count += 1
                logger.debug(f"清理加密密钥缓存: lookup_code={lookup_code}, uploader_ip={uploader_ip}")

        # 4. 清理映射关系（内存和Redis）
        for lookup_code in all_lookup_codes:
            # 清理内存映射关系
            if lookup_code in lookup_code_mapping:
                del lookup_code_mapping[lookup_code]
                cleaned_count += 1
                logger.debug(f"清理内存映射关系: lookup_code={lookup_code}")

            # 清理Redis映射关系
            if cache_manager.exists('lookup_mapping', lookup_code):
                cache_manager.delete('lookup_mapping', lookup_code)
                cleaned_count += 1
                logger.debug(f"清理Redis映射关系: lookup_code={lookup_code}")

        logger.info(f"文件缓存清理完成: 清理了 {cleaned_count} 个缓存项")
        return cleaned_count
