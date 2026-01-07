from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException
from fastapi.responses import JSONResponse
import hashlib
from app.models.pickup_code import PickupCode
from app.utils.pickup_code import ensure_aware_datetime, check_and_update_expired_pickup_code
from app.utils.validation import validate_pickup_code
from app.utils.response import success_response, bad_request_response, not_found_response
from app.utils.cache import cache_manager
from app.services.pickup_code_service import get_pickup_code_by_lookup
from app.services.mapping_service import get_original_lookup_code, update_cache_expire_at
from app.services.cache_service import chunk_cache, file_info_cache
from app.services.pool_service import upload_pool
import logging

logger = logging.getLogger(__name__)

async def upload_chunk(
    code: str,
    chunk_data: UploadFile,
    chunk_index: Optional[int],
    chunk_index_query: Optional[int],
    db: Session,
    current_user
):
    """
    上传加密的文件块（流式传输）
    
    注意：chunk_index 可以作为 Form 数据或查询参数传递（兼容性处理）
    """
    # 兼容处理：优先使用 Form 数据，如果没有则使用查询参数
    if chunk_index is None:
        if chunk_index_query is None:
            raise HTTPException(
                status_code=422,
                detail="chunk_index 必须作为 Form 数据或查询参数提供"
            )
        chunk_index = chunk_index_query
    """
    上传加密的文件块（流式传输）
    
    特点：
    - 文件块在客户端加密后上传
    - 服务器只存储加密后的数据，无法查看内容
    - 数据存储在内存中，不写入磁盘
    - 支持一对多：多个接收者可以同时下载
    """
    # 检查权限：只有登录用户才能上传文件块
    if not current_user:
        return bad_request_response(
            msg="只有登录用户才能上传文件块",
            data={"code": "UNAUTHORIZED", "status": "unauthorized"}
        )
    
    # 验证取件码（服务器只接收6位查找码）
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误，必须为6位大写字母或数字")
    
    # 使用查找码查询取件码（服务器只接收6位查找码，不接触后6位密钥码）
    pickup_code = get_pickup_code_by_lookup(db, code)
    if not pickup_code:
        return not_found_response(msg=f"取件码不存在")
    
    # 检查并更新过期状态
    is_expired = check_and_update_expired_pickup_code(pickup_code, db)
    if is_expired or pickup_code.status == "expired":
        return bad_request_response(
            msg="取件码已过期，无法使用",
            data={"code": "EXPIRED", "status": "expired"}
        )
    
    if pickup_code.status == "completed":
        return bad_request_response(
            msg="取件码已完成，无法使用",
            data={"code": "COMPLETED", "status": "completed"}
        )
    
    # 检查使用次数限制
    used_count = pickup_code.used_count or 0
    limit_count = pickup_code.limit_count or 3
    if limit_count != 999 and used_count >= limit_count:
        return bad_request_response(
            msg="取件码已达到使用上限，无法继续使用",
            data={
                "code": "LIMIT_REACHED",
                "usedCount": used_count,
                "limitCount": limit_count,
                "remaining": 0
            }
        )
    
    # 清理过期块
    # 注意：不再每次清理，改为定时清理（后台任务）
    # cleanup_expired_chunks(db)  # 已移除，改为定时清理
    
    # code 就是查找码（6位），直接用作缓存键
    lookup_code = code
    
    # 检查是否存在映射，如果存在则使用原始的 lookup_code 访问缓存
    original_lookup_code = get_original_lookup_code(lookup_code, db)
    
    # 获取原始上传者的 user_id（文件块缓存是用这个 user_id 存储的）
    # 从数据库获取文件的上传者ID
    original_uploader_id = None
    try:
        from app.models.file import File
        file_record = db.query(File).filter(File.id == pickup_code.file_id).first()
        if file_record and file_record.uploader_id:
            original_uploader_id = file_record.uploader_id
    except Exception as e:
        logger.debug(f"无法获取上传者ID: {e}")
        # 如果无法获取，回退到当前用户的ID
        original_uploader_id = current_user.id if current_user else None
    
    # 读取加密后的数据块
    encrypted_data = await chunk_data.read()
    
    if not encrypted_data:
        return bad_request_response(msg="文件块数据为空")
    
    # 计算数据块哈希（用于验证完整性）
    chunk_hash = hashlib.sha256(encrypted_data).hexdigest()
    
    # 检查文件块是否已存在（通过映射表，可能已有缓存）
    # 如果已存在且未过期，直接返回成功，不重复存储
    # 使用原始上传者的 user_id 查找缓存（因为缓存是用这个 user_id 存储的）
    if chunk_cache.exists(original_lookup_code, original_uploader_id):
        chunks = chunk_cache.get(original_lookup_code, original_uploader_id)
        if chunk_index in chunks:
            existing_chunk = chunks[chunk_index]
            # 检查是否过期（使用取件码的过期时间，绝对时间）
            pickup_expire_at = existing_chunk.get('pickup_expire_at') or existing_chunk.get('expires_at')
            if pickup_expire_at:
                pickup_expire_at = ensure_aware_datetime(pickup_expire_at)
                if datetime.now(timezone.utc) < pickup_expire_at:
                    # 文件块已存在且未过期，更新过期时间为最晚的过期时间，然后返回成功（复用现有块）
                    logger.info(f"文件块 {chunk_index} 已存在（通过映射表复用），更新过期时间并跳过上传")
                    # 更新缓存的过期时间（取所有相关取件码中最晚的过期时间）
                    update_cache_expire_at(original_lookup_code, pickup_code.expire_at, db, original_uploader_id)
                # 获取更新后的过期时间
                updated_chunks = chunk_cache.get(original_lookup_code, original_uploader_id)
                updated_expire_at = updated_chunks[chunk_index].get('pickup_expire_at') or updated_chunks[chunk_index].get('expires_at')
                return success_response(
                    msg="文件块已存在（复用），无需重复上传",
                    data={
                        "chunkIndex": chunk_index,
                        "chunkHash": existing_chunk['hash'],
                        "reused": True,  # 标记为复用
                        "expiresAt": updated_expire_at.isoformat() + "Z"
                    }
                )
    
    # ========== 优化方案：使用临时上传池 ==========
    # 先写入临时池（内存操作，快速），完成后再批量写入主缓存
    logger.debug(f"[upload-chunk] 开始上传块: lookup_code={lookup_code}, original_lookup_code={original_lookup_code}, chunk_index={chunk_index}")
    
    # 检查是否已存在（通过映射表复用）
    # 使用原始上传者的 user_id 查找缓存（因为缓存是用这个 user_id 存储的）
    if chunk_cache.exists(original_lookup_code, original_uploader_id):
        chunks = chunk_cache.get(original_lookup_code, original_uploader_id)
        if chunk_index in chunks:
            existing_chunk = chunks[chunk_index]
            # 检查是否过期
            pickup_expire_at = existing_chunk.get('pickup_expire_at') or existing_chunk.get('expires_at')
            if pickup_expire_at:
                pickup_expire_at = ensure_aware_datetime(pickup_expire_at)
                if datetime.now(timezone.utc) < pickup_expire_at:
                    # 文件块已存在且未过期，更新过期时间并返回成功（复用现有块）
                    logger.info(f"[upload-chunk] 文件块 {chunk_index} 已存在（通过映射表复用），更新过期时间并跳过上传")
                    update_cache_expire_at(original_lookup_code, pickup_code.expire_at, db, original_uploader_id)
                    updated_chunks = chunk_cache.get(original_lookup_code, original_uploader_id)
                    updated_expire_at = updated_chunks[chunk_index].get('pickup_expire_at') or updated_chunks[chunk_index].get('expires_at')
                    return success_response(
                        msg="文件块已存在（复用），无需重复上传",
                        data={
                            "chunkIndex": chunk_index,
                            "chunkHash": existing_chunk['hash'],
                            "reused": True,
                            "expiresAt": updated_expire_at.isoformat() + "Z"
                        }
                    )
    
    # 确定过期时间
    # 使用原始上传者的 user_id 查找缓存（因为缓存是用这个 user_id 存储的）
    if chunk_cache.exists(original_lookup_code, original_uploader_id):
        chunks = chunk_cache.get(original_lookup_code, original_uploader_id)
        if chunks:
            # 复用文件，使用已有块的过期时间
            first_chunk = next(iter(chunks.values()))
            pickup_expire_at = first_chunk.get('pickup_expire_at') or first_chunk.get('expires_at')
        else:
            # 新文件，使用当前取件码的过期时间
            pickup_expire_at = pickup_code.expire_at
    else:
        # 新文件，使用当前取件码的过期时间
        pickup_expire_at = pickup_code.expire_at
    
    # 写入临时上传池（内存操作，快速）
    if original_lookup_code not in upload_pool:
        upload_pool[original_lookup_code] = {}
    
    upload_pool[original_lookup_code][chunk_index] = {
        'data': encrypted_data,
        'hash': chunk_hash,
        'created_at': datetime.now(timezone.utc),
        'pickup_expire_at': pickup_expire_at,
        'expires_at': pickup_expire_at
    }
    
    logger.debug(f"[upload-chunk] ✓ 块 {chunk_index} 已写入临时池: original_lookup_code={original_lookup_code}, 池中块数量={len(upload_pool[original_lookup_code])}")
    
    return success_response(
        msg="文件块上传成功（已加密存储）",
        data={
            "chunkIndex": chunk_index,
            "chunkHash": chunk_hash,
            "expiresAt": pickup_expire_at.isoformat() + "Z"
        }
    )


async def upload_complete(
    code: str,
    request,
    db: Session,
    current_user
):
    """
    通知服务器上传完成
    
    存储文件元信息，供接收者查询
    
    重要：此接口只用于通知上传完成，不会自动创建取件码。
    取件码必须在用户明确点击"生成取件码"按钮时，通过 /api/v1/codes POST 接口创建。
    """
    # 检查权限：只有登录用户才能调用此接口
    if not current_user:
        return bad_request_response(
            msg="只有登录用户才能调用此接口",
            data={"code": "UNAUTHORIZED", "status": "unauthorized"}
        )
    
    # 验证取件码（服务器只接收6位查找码）
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误，必须为6位大写字母或数字")
    
    # 使用查找码查询取件码（服务器只接收6位查找码，不接触后6位密钥码）
    pickup_code = get_pickup_code_by_lookup(db, code)
    if not pickup_code:
        return not_found_response(msg=f"取件码不存在")
    
    # 提取查找码（前6位）用于缓存键
    # code 就是查找码（6位），直接用作缓存键
    lookup_code = code
    
    # 获取原始上传者的 user_id（文件块缓存是用这个 user_id 存储的）
    # 从数据库获取文件的上传者ID
    original_uploader_id = None
    try:
        from app.models.file import File
        file_record = db.query(File).filter(File.id == pickup_code.file_id).first()
        if file_record and file_record.uploader_id:
            original_uploader_id = file_record.uploader_id
    except Exception as e:
        logger.debug(f"无法获取上传者ID: {e}")
        # 如果无法获取，回退到当前用户的ID
        original_uploader_id = current_user.id if current_user else None
    
    # 检查是否存在映射，如果存在则使用原始的 lookup_code 访问缓存
    original_lookup_code = get_original_lookup_code(lookup_code, db)
    
    # ========== 上传完成检查：验证临时上传池并批量写入主缓存 ==========
    logger.info(f"[upload-complete] ========== 开始验证上传完成 ==========")
    logger.info(f"[upload-complete] lookup_code={lookup_code}, original_lookup_code={original_lookup_code}")
    logger.info(f"[upload-complete] 文件信息: fileName={request.fileName}, fileSize={request.fileSize}, totalChunks={request.totalChunks}")
    
    # 首先检查临时上传池
    pool_chunks = None
    if original_lookup_code in upload_pool:
        pool_chunks = upload_pool[original_lookup_code]
        pool_chunk_count = len(pool_chunks)
        pool_chunk_indices = sorted(pool_chunks.keys())
        
        logger.info(f"[upload-complete] ✓ 找到临时上传池: original_lookup_code={original_lookup_code}")
        logger.info(f"[upload-complete] 临时池中的块数量: {pool_chunk_count}, 期望的块数量: {request.totalChunks}")
        logger.info(f"[upload-complete] 临时池中的块索引: {pool_chunk_indices}")
        
        # 验证临时池的完整性
        expected_indices = set(range(request.totalChunks))
        pool_indices_set = set(pool_chunk_indices)
        missing_indices = expected_indices - pool_indices_set
        extra_indices = pool_indices_set - expected_indices
        
        if missing_indices:
            logger.error(f"[upload-complete] ✗ 临时池验证失败: 缺失 {len(missing_indices)} 个块: {sorted(missing_indices)}")
            # 清理临时池
            del upload_pool[original_lookup_code]
            return bad_request_response(
                msg=f"文件上传不完整，缺失 {len(missing_indices)} 个块",
                data={
                    "code": "INCOMPLETE_UPLOAD",
                    "missingChunks": sorted(missing_indices),
                    "extraChunks": sorted(extra_indices),
                    "totalChunks": request.totalChunks,
                    "poolChunks": pool_chunk_count
                }
            )
        
        if extra_indices:
            logger.warning(f"[upload-complete] ⚠️ 临时池中有多余的块: {sorted(extra_indices)}")
        
        if pool_chunk_count != request.totalChunks:
            logger.error(f"[upload-complete] ✗ 临时池块数量不匹配: 池中有 {pool_chunk_count} 个块，但期望 {request.totalChunks} 个块")
            del upload_pool[original_lookup_code]
            return bad_request_response(
                msg=f"文件上传不完整，块数量不匹配",
                data={
                    "code": "INCOMPLETE_UPLOAD",
                    "totalChunks": request.totalChunks,
                    "poolChunks": pool_chunk_count
                }
            )
        
        logger.info(f"[upload-complete] ✓ 临时池验证通过: {pool_chunk_count}/{request.totalChunks} 个块完整")
        
        # 验证通过，批量写入主缓存（只写一次，性能优化）
        try:
            # 合并到主缓存（如果已存在部分块，合并；否则直接写入）
            # 使用原始上传者的 user_id（因为缓存是用这个 user_id 存储的）
            if chunk_cache.exists(original_lookup_code, original_uploader_id):
                # 合并已有块和新块
                existing_chunks = chunk_cache.get(original_lookup_code, original_uploader_id)
                existing_chunks.update(pool_chunks)
                chunks_to_save = existing_chunks
                logger.info(f"[upload-complete] 合并到已有缓存: 原有 {len(existing_chunks) - len(pool_chunks)} 个块，新增 {len(pool_chunks)} 个块")
            else:
                # 直接写入新块
                chunks_to_save = pool_chunks.copy()
                logger.info(f"[upload-complete] 写入新缓存: {len(chunks_to_save)} 个块")
            
            # 批量写入主缓存（只写一次，大幅提升性能）
            # 使用原始上传者的 user_id（因为缓存是用这个 user_id 存储的）
            chunk_cache.set(original_lookup_code, chunks_to_save, original_uploader_id)
            logger.info(f"[upload-complete] ✓ 批量写入主缓存成功: {len(chunks_to_save)} 个块")
            
            # 清理临时池
            del upload_pool[original_lookup_code]
            logger.info(f"[upload-complete] ✓ 临时池已清理")
            
        except Exception as e:
            logger.error(f"[upload-complete] ✗ 批量写入主缓存失败: {e}", exc_info=True)
            # 清理临时池
            if original_lookup_code in upload_pool:
                del upload_pool[original_lookup_code]
            raise
    
    # 检查文件块缓存（用于复用文件的情况）
    # 使用原始上传者的 user_id 查找缓存（因为缓存是用这个 user_id 存储的）
    elif chunk_cache.exists(original_lookup_code, original_uploader_id):
        cached_chunks = chunk_cache.get(original_lookup_code, original_uploader_id)
        cached_chunk_count = len(cached_chunks)
        cached_chunk_indices = sorted(cached_chunks.keys())
        
        logger.info(f"[upload-complete] ✓ 找到文件块缓存: original_lookup_code={original_lookup_code}")
        logger.info(f"[upload-complete] 缓存中的块数量: {cached_chunk_count}, 期望的块数量: {request.totalChunks}")
        logger.info(f"[upload-complete] 缓存中的块索引: {cached_chunk_indices}")
        
        # 验证块数量
        if cached_chunk_count != request.totalChunks:
            logger.warning(f"[upload-complete] ⚠️ 块数量不匹配: 缓存中有 {cached_chunk_count} 个块，但期望 {request.totalChunks} 个块")
        
        # 验证块索引是否连续（从 0 到 totalChunks-1）
        expected_indices = set(range(request.totalChunks))
        cached_indices_set = set(cached_chunk_indices)
        missing_indices = expected_indices - cached_indices_set
        extra_indices = cached_indices_set - expected_indices
        
        if missing_indices:
            logger.warning(f"[upload-complete] ⚠️ 缺失的块索引: {sorted(missing_indices)}")
        if extra_indices:
            logger.warning(f"[upload-complete] ⚠️ 多余的块索引: {sorted(extra_indices)}")
        
        if not missing_indices and not extra_indices and cached_chunk_count == request.totalChunks:
            logger.info(f"[upload-complete] ✓ 所有块验证通过: {cached_chunk_count}/{request.totalChunks} 个块已正确存储")
        else:
            logger.error(f"[upload-complete] ✗ 块验证失败: 缺失 {len(missing_indices)} 个块，多余 {len(extra_indices)} 个块")
            # 返回错误响应，让客户端知道上传不完整
            return bad_request_response(
                msg=f"文件上传不完整，缺失 {len(missing_indices)} 个块",
                data={
                    "code": "INCOMPLETE_UPLOAD",
                    "missingChunks": sorted(missing_indices),
                    "extraChunks": sorted(extra_indices),
                    "totalChunks": request.totalChunks,
                    "cachedChunks": cached_chunk_count
                }
            )
        
        # 检查每个块的数据大小
        total_data_size = 0
        for chunk_index in cached_chunk_indices:
            chunk_data = cached_chunks[chunk_index].get('data')
            if chunk_data:
                chunk_size = len(chunk_data) if isinstance(chunk_data, bytes) else 0
                total_data_size += chunk_size
                logger.debug(f"[upload-complete] 块 {chunk_index}: 大小={chunk_size} 字节, 哈希={cached_chunks[chunk_index].get('hash', 'N/A')[:16]}...")
        
        logger.info(f"[upload-complete] 所有块的总数据大小: {total_data_size} 字节")
        
    else:
        # 既不在临时池，也不在主缓存
        logger.error(f"[upload-complete] ✗ 文件块不存在: original_lookup_code={original_lookup_code}")
        logger.error(f"[upload-complete] 临时池中的键: {list(upload_pool.keys())}")
        logger.error(f"[upload-complete] 主缓存中的键: {list(chunk_cache.keys())}")
        return bad_request_response(
            msg="文件块不存在，上传可能未完成",
            data={
                "code": "CHUNKS_NOT_FOUND",
                "originalLookupCode": original_lookup_code,
                "totalChunks": request.totalChunks,
                "uploadPoolKeys": list(upload_pool.keys()),
                "cacheKeys": list(chunk_cache.keys())
            }
        )
    
    # 检查文件信息缓存
    # 使用原始上传者的 user_id（因为缓存是用这个 user_id 存储的）
    if file_info_cache.exists(original_lookup_code, original_uploader_id):
        logger.info(f"[upload-complete] ✓ 文件信息缓存已存在: original_lookup_code={original_lookup_code}")
        existing_file_info = file_info_cache.get(original_lookup_code, original_uploader_id)
        logger.info(f"[upload-complete] 现有文件信息: fileName={existing_file_info.get('fileName')}, totalChunks={existing_file_info.get('totalChunks')}")
    else:
        logger.info(f"[upload-complete] 文件信息缓存不存在，将创建新的缓存条目")
    
    # 存储文件信息
    # 使用原始的查找码作为键，支持多个 lookup_code 共享同一个文件信息缓存
    # 如果已存在缓存（复用文件），更新过期时间为所有相关取件码中最晚的过期时间
    # 使用原始上传者的 user_id（因为缓存是用这个 user_id 存储的）
    if file_info_cache.exists(original_lookup_code, original_uploader_id):
        # 复用文件：更新过期时间为最晚的过期时间
        update_cache_expire_at(original_lookup_code, pickup_code.expire_at, db, original_uploader_id)
        logger.info(f"[upload-complete] 更新文件信息缓存的过期时间")
    else:
        # 新文件：使用当前取件码的过期时间
        # 使用原始上传者的 user_id（因为缓存是用这个 user_id 存储的）
        file_info_cache.set(original_lookup_code, {
            'fileName': request.fileName,
            'fileSize': request.fileSize,
            'mimeType': request.mimeType,
            'totalChunks': request.totalChunks,
            'uploadedAt': datetime.now(timezone.utc),
            'pickup_expire_at': pickup_code.expire_at,  # 取件码的过期时间（绝对时间）
            # 标识码信息：标识码与文件缓存强绑定，用于稳定访问共享缓存
            'identifier_code': original_lookup_code,
            'identifier_expire_at': pickup_code.expire_at
        }, original_uploader_id)
        logger.info(f"[upload-complete] ✓ 文件信息已存储到缓存")
    
    logger.info(f"[upload-complete] ========== 上传完成验证结束 ==========")
    
    return success_response(
        msg="上传完成通知已接收",
        data={
            "code": code,
            "totalChunks": request.totalChunks,
            "fileSize": request.fileSize,
            "fileName": request.fileName
        }
    )