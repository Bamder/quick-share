from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.pickup_code import PickupCode
from app.utils.cache import cache_manager
from app.utils.pickup_code import ensure_aware_datetime, DatetimeUtil
from app.services.cache_service import chunk_cache, file_info_cache, encrypted_key_cache, _make_cache_key
import logging

logger = logging.getLogger(__name__)

lookup_code_mapping = {}
# 缓存标识码重建失败的 lookup_code，避免反复重建
_failed_identifier_lookups = set()


def clear_failed_lookups():
    """清理失败标记（主要用于测试）"""
    _failed_identifier_lookups.clear()


def save_lookup_mapping(lookup_code: str, original_lookup_code: str, expire_at: Optional[datetime] = None):
    """
    保存查找码映射关系到Redis和内存
    
    参数:
    - lookup_code: 当前查找码（6位）
    - original_lookup_code: 标识码（6位，最初的取件码；与文件缓存强绑定）
    - expire_at: 过期时间（可选，用于设置Redis过期时间）
    """
    # 保存到Redis（持久化）
    cache_manager.set('lookup_mapping', lookup_code, original_lookup_code, expire_at=expire_at)
    
    # 保存到内存（活跃映射）
    lookup_code_mapping[lookup_code] = original_lookup_code
    logger.debug(f"保存映射关系: {lookup_code} -> {original_lookup_code} (Redis + 内存)")


def get_identifier_code(lookup_code: str, db: Session = None, context: str = "unknown") -> Optional[str]:
    """
    获取文件的"标识码"（identifier_code）：
    - 与第一个创建的取件码值一致（6位），但不是同一实体
    - 与文件缓存强绑定：文件缓存延时 => 标识码延时；文件缓存过期 => 标识码过期
    - 所有取件码（含后续新生成的）都映射到该标识码上以访问共享的文件缓存

    解析策略：
    1) 先查内存映射；2) 再查Redis映射；3) 最后用数据库重建：优先最早"未过期"的取件码；
       若都过期，则不重建标识码（标识码机制：无活跃取件码时标识码不存在）
    
    返回:
    - 标识码字符串，如果找到
    - None，如果找不到或所有取件码都已过期
    """
    # 验证输入：空字符串或无效查找码应返回 None
    if not lookup_code or not isinstance(lookup_code, str) or len(lookup_code) != 6:
        logger.info(f"[{context}] 无效的查找码: lookup_code={lookup_code!r}, type={type(lookup_code)}, len={len(lookup_code) if lookup_code else 0}")
        return None

    # 调试：检查内存映射
    logger.info(f"[{context}] 查找标识码: lookup_code={lookup_code}, 内存映射中有: {list(lookup_code_mapping.keys())}, 失败标记中有: {list(_failed_identifier_lookups)}")

    # 1. 内存（优先检查，因为内存映射是活跃的）
    if lookup_code in lookup_code_mapping:
        identifier_code = lookup_code_mapping[lookup_code]
        logger.info(f"[{context}] 从内存获取标识码: {lookup_code} -> {identifier_code}")
        # 如果提供了 db，检查过期时间
        if db:
            logger.info(f"[{context}] 提供了 db，检查过期时间")
            try:
                pickup_code = db.query(PickupCode).filter(PickupCode.code == lookup_code).first()
                if pickup_code and pickup_code.expire_at:
                    expire_at = ensure_aware_datetime(pickup_code.expire_at)
                    now = DatetimeUtil.now()
                    if expire_at <= now:
                        # 已过期，从内存中删除并返回 None
                        logger.info(f"[{context}] 内存映射已过期: lookup_code={lookup_code}, expire_at={expire_at}")
                        del lookup_code_mapping[lookup_code]
                        _failed_identifier_lookups.add(lookup_code)
                        return None
            except Exception as e:
                logger.warning(f"检查内存映射过期时间失败: {e}")
        logger.info(f"[{context}] 返回内存中的标识码: {identifier_code}")
        return identifier_code
    else:
        logger.info(f"[{context}] 内存映射中未找到: {lookup_code}")
    
    # 检查是否已经确定此lookup_code无法重建标识码（在检查内存之后）
    if lookup_code in _failed_identifier_lookups:
        logger.debug(f"[{context}] 跳过标识码重建（已确认失败）: lookup_code={lookup_code}")
        return None

    # 2. Redis
    cached_mapping = cache_manager.get('lookup_mapping', lookup_code)
    if cached_mapping:
        identifier_code = cached_mapping
        lookup_code_mapping[lookup_code] = identifier_code
        logger.debug(f"从Redis加载映射关系到内存: {lookup_code} -> {identifier_code}")
        return identifier_code

    # 3. 数据库重建
    if db:
        try:
            from app.utils.pickup_code import check_and_update_expired_pickup_code

            pickup_code = db.query(PickupCode).filter(PickupCode.code == lookup_code).first()
            if pickup_code:
                now = DatetimeUtil.now()
                # 优先最早的"未过期"的取件码作为标识码（在Python中检查时区）
                all_candidates = db.query(PickupCode).filter(
                    PickupCode.file_id == pickup_code.file_id,
                    PickupCode.status.in_(["waiting", "transferring"])
                ).order_by(PickupCode.created_at.asc()).all()

                candidate = None
                for cand in all_candidates:
                    if cand.expire_at:
                        cand_expire_at = ensure_aware_datetime(cand.expire_at)
                        if cand_expire_at > now:
                            candidate = cand
                            break

                # 如果没有未过期的取件码，不重建标识码（标识码机制：无活跃取件码时标识码不存在）
                if not candidate:
                    logger.warning(
                        f"[{context}] 标识码重建失败：文件 {pickup_code.file_id} 的所有取件码均已过期，无法重建标识码 (lookup_code={lookup_code})"
                    )
                    # 记录失败，避免反复重建
                    _failed_identifier_lookups.add(lookup_code)
                    return None

                if candidate:
                    identifier_code = candidate.code
                    expire_at = ensure_aware_datetime(pickup_code.expire_at) if pickup_code.expire_at else None
                    save_lookup_mapping(lookup_code, identifier_code, expire_at)
                    logger.info(f"从数据库重建标识码映射: {lookup_code} -> {identifier_code} (状态={candidate.status})")
                    return identifier_code
        except Exception as e:
            logger.warning(f"从数据库重建标识码映射失败: {e}")

    # 4. 找不到映射关系，返回 None（不再使用自映射兜底）
    logger.debug(f"[{context}] 未找到查找码映射: lookup_code={lookup_code}")
    return None


def get_original_lookup_code(lookup_code: str, db: Session = None) -> Optional[str]:
    """
    兼容旧接口：等价于 get_identifier_code
    """
    return get_identifier_code(lookup_code, db)


def get_all_related_lookup_codes(original_lookup_code: str, db: Session = None) -> list:
    """
    获取所有映射到同一个 original_lookup_code 的 lookup_code 列表
    
    参数:
    - original_lookup_code: 原始查找码（6位）
    - db: 数据库会话（可选，用于从数据库查询）
    
    返回:
    - 相关的 lookup_code 列表
    """
    related_codes = []
    
    # 1. 从内存映射表查找
    for lookup_code, orig_code in lookup_code_mapping.items():
        if orig_code == original_lookup_code:
            related_codes.append(lookup_code)
    
    # 2. 从数据库查找（如果提供了db）
    if db:
        try:
            # 查询所有映射到同一个文件的取件码
            original_pickup_code = db.query(PickupCode).filter(
                PickupCode.code == original_lookup_code
            ).first()
            
            if original_pickup_code:
                # 查询同一个文件的所有取件码
                all_pickup_codes = db.query(PickupCode).filter(
                    PickupCode.file_id == original_pickup_code.file_id
                ).all()
                
                for pickup_code in all_pickup_codes:
                    if pickup_code.code not in related_codes:
                        related_codes.append(pickup_code.code)
        except Exception as e:
            logger.warning(f"从数据库查询相关查找码失败: {e}")
    
    return related_codes


def get_max_expire_at_for_original_lookup_code(original_lookup_code: str, db: Session) -> Optional[datetime]:
    """
    获取所有映射到同一个 original_lookup_code 的取件码中最晚的过期时间
    
    参数:
    - original_lookup_code: 原始查找码（6位）
    - db: 数据库会话
    
    返回:
    - 最晚的过期时间，如果没有找到未过期的取件码则返回 None
    - 注意：只返回未过期（status in ["waiting", "transferring"]）的取件码的最晚过期时间
    """
    # 找到所有映射到 original_lookup_code 的 lookup_code
    related_lookup_codes = get_all_related_lookup_codes(original_lookup_code, db)
    
    if not related_lookup_codes:
        return None
    
    # 查询这些取件码中未过期的（status in ["waiting", "transferring"]）
    pickup_codes = db.query(PickupCode).filter(
        PickupCode.code.in_(related_lookup_codes),
        PickupCode.status.in_(["waiting", "transferring"])  # 只考虑有效的取件码
    ).all()
    
    if not pickup_codes:
        # 所有取件码都已过期或完成，返回 None
        return None
    
    # 找到最晚的过期时间，并确保是 aware datetime
    max_expire_at = max(pickup_code.expire_at for pickup_code in pickup_codes)
    return ensure_aware_datetime(max_expire_at) if max_expire_at else None

def check_all_pickup_codes_expired_for_file(file_id: int, db: Session) -> bool:
    """
    检查文件的所有取件码是否都已过期（status == "expired"）
    
    参数:
    - file_id: 文件ID
    - db: 数据库会话
    
    返回:
    - True: 所有取件码都已过期
    - False: 还有未过期的取件码
    """
    # 查询该文件的所有取件码
    all_pickup_codes = db.query(PickupCode).filter(
        PickupCode.file_id == file_id
    ).all()
    
    if not all_pickup_codes:
        # 没有取件码，认为已过期
        return True
    
    # 检查是否所有取件码都已过期
    for pickup_code in all_pickup_codes:
        # 检查状态是否为过期
        if pickup_code.status != "expired":
            # 如果状态不是过期，检查是否实际过期
            if pickup_code.expire_at:
                expire_at = ensure_aware_datetime(pickup_code.expire_at)
                now = datetime.now(timezone.utc)
                if now <= expire_at:
                    # 还有未过期的取件码
                    return False
            else:
                # 没有过期时间，认为未过期
                return False
    
    # 所有取件码都已过期
    return True


def update_cache_expire_at(original_lookup_code: str, new_expire_at: datetime, db: Session, user_id: Optional[int] = None):
    """
    更新缓存的过期时间（取所有相关取件码中最晚的过期时间）
    
    参数:
    - original_lookup_code: 标识码（6位）
    - new_expire_at: 新取件码的过期时间
    - db: 数据库会话
    - user_id: 用户ID（用于缓存隔离）
    """
    # 获取所有相关取件码中最晚的过期时间
    max_expire_at = get_max_expire_at_for_original_lookup_code(original_lookup_code, db)
    
    # 确保两个 datetime 都是 aware 的，以便比较
    new_expire_at = ensure_aware_datetime(new_expire_at)
    if max_expire_at:
        max_expire_at = ensure_aware_datetime(max_expire_at)
    
    # 如果找到了更晚的过期时间，使用它；否则使用新取件码的过期时间
    if max_expire_at and max_expire_at > new_expire_at:
        expire_at = max_expire_at
        logger.info(f"更新缓存过期时间: original_lookup_code={original_lookup_code}, user_id={user_id}, 使用最晚过期时间={expire_at}（新码={new_expire_at}）")
    else:
        expire_at = new_expire_at
        logger.info(f"更新缓存过期时间: original_lookup_code={original_lookup_code}, user_id={user_id}, 使用新码过期时间={expire_at}")
    
    # 更新文件块缓存的过期时间（并写入标识码过期时间，便于诊断）
    if chunk_cache.exists(original_lookup_code, user_id):
        chunks = chunk_cache.get(original_lookup_code, user_id)
        for chunk_index, chunk_data in chunks.items():
            chunk_data['pickup_expire_at'] = expire_at
            chunk_data['expires_at'] = expire_at
            # 诊断用途：同步一份标识码过期字段（不作为判断依据）
            chunk_data['identifier_expire_at'] = expire_at
        # 重新保存到缓存（更新过期时间）
        chunk_cache.set(original_lookup_code, chunks, user_id)
    
    # 更新文件信息缓存的过期时间（并写入/刷新标识码及其过期时间）
    if file_info_cache.exists(original_lookup_code, user_id):
        file_info = file_info_cache.get(original_lookup_code, user_id)
        file_info['pickup_expire_at'] = expire_at
        file_info['identifier_code'] = original_lookup_code
        file_info['identifier_expire_at'] = expire_at
        # 重新保存到缓存（更新过期时间）
        file_info_cache.set(original_lookup_code, file_info, user_id)
    
    # 注意：不更新加密密钥缓存的过期时间
    # 原因：
    # 1. 每个取件码的密钥应该独立过期，使用各自取件码的过期时间
    # 2. 不应该因为复用文件就把旧取件码的密钥缓存也延时
    # 3. 密钥缓存的过期时间在存储时就已经设置为对应取件码的过期时间
    # 4. 这样保持数据库记录和密钥缓存的一致性