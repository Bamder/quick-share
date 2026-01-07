from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
import io
import uuid
from fastapi.responses import StreamingResponse, JSONResponse
from app.models.pickup_code import PickupCode
from app.utils.pickup_code import ensure_aware_datetime, check_and_update_expired_pickup_code
from app.utils.validation import validate_pickup_code
from app.utils.response import success_response, bad_request_response, not_found_response
from app.services.pickup_code_service import get_pickup_code_by_lookup
from app.services.mapping_service import get_original_lookup_code
from app.services.cache_service import chunk_cache, file_info_cache
from app.services.pool_service import download_pool, preload_next_chunks
import logging

logger = logging.getLogger(__name__)

active_download_sessions = {}

async def download_chunk(
    code: str,
    chunk_index: int,
    session_id: Optional[str],
    db: Session
):
    """
    下载加密的文件块（流式传输）
    
    特点：
    - 返回加密后的数据块
    - 客户端解密后重组文件
    - 支持多个接收者同时下载
    - 数据从内存读取，不涉及磁盘
    
    注意：如果提供了session_id，会验证是否是已开始的下载会话
    如果是已开始的下载会话，允许继续下载（即使达到上限）
    """
    # 验证取件码（服务器只接收6位查找码）
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误，必须为6位大写字母或数字")
    
    # 使用查找码查询取件码（服务器只接收6位查找码，不接触后6位密钥码）
    pickup_code = get_pickup_code_by_lookup(db, code)
    if not pickup_code:
        return not_found_response(msg=f"取件码不存在")
    
    # 如果提供了session_id，验证是否是已开始的下载会话
    # 如果是已开始的下载会话，允许继续下载（不检查使用次数限制）
    lookup_code = code
    original_lookup_code = get_original_lookup_code(lookup_code, db)
    
    if session_id:
        # 验证会话ID是否有效
        if original_lookup_code in active_download_sessions:
            if session_id not in active_download_sessions[original_lookup_code]:
                # 会话ID无效，可能是旧的会话或无效的会话
                logger.warning(f"无效的下载会话ID: lookup_code={lookup_code}, session_id={session_id}")
                # 不拒绝，允许继续（可能是旧的实现没有session_id）
        # 如果是有效的会话，允许继续下载（不检查使用次数限制）
    else:
        # 没有提供session_id，这是新的下载请求
        # 检查使用次数限制（只检查已完成的下载次数）
        used_count = pickup_code.used_count or 0
        limit_count = pickup_code.limit_count or 3
        
        # 如果已完成的下载次数已达到上限，拒绝新的下载请求
        if limit_count != 999 and used_count >= limit_count:
            return bad_request_response(
                msg="取件码已达到使用上限，无法继续使用",
                data={
                    "code": "LIMIT_REACHED",
                    "usedCount": used_count,
                    "activeCount": 0,  # 新请求还没有活跃会话
                    "limitCount": limit_count,
                    "remaining": 0
                }
            )
        
        # 生成新的下载会话ID（用于跟踪这个下载）
        import uuid
        session_id = str(uuid.uuid4())
        
        # 记录这个下载会话（真正开始下载块时才添加）
        if original_lookup_code not in active_download_sessions:
            active_download_sessions[original_lookup_code] = set()
        active_download_sessions[original_lookup_code].add(session_id)
        logger.info(f"开始下载会话: lookup_code={lookup_code}, session_id={session_id}, chunk_index={chunk_index}, active_count={len(active_download_sessions[original_lookup_code])}")
    
    # 提取查找码（前6位）用于缓存键
    # code 就是查找码（6位），直接用作缓存键
    lookup_code = code
    
    # 获取用户ID（用于缓存隔离）
    # 从数据库获取文件的上传者ID
    user_id = None
    try:
        from app.models.file import File
        file_record = db.query(File).filter(File.id == pickup_code.file_id).first()
        if file_record and file_record.uploader_id:
            user_id = file_record.uploader_id
    except Exception as e:
        logger.debug(f"无法获取上传者ID: {e}")
    
    # 检查是否存在映射，如果存在则使用原始的 lookup_code 访问缓存
    original_lookup_code = get_original_lookup_code(lookup_code, db)
    
    # 注意：不再每次清理，改为定时清理（后台任务）
    # cleanup_expired_chunks(db)  # 已移除，改为定时清理
    
    # 确保有session_id（如果没有，使用之前生成的）
    if not session_id:
        # 如果没有session_id，生成一个（这种情况不应该发生，但为了安全）
        session_id = str(uuid.uuid4())
        if original_lookup_code not in active_download_sessions:
            active_download_sessions[original_lookup_code] = set()
        active_download_sessions[original_lookup_code].add(session_id)
        logger.warning(f"[download-chunk] 生成了新的session_id: {session_id}")
    
    # 从下载池或主缓存读取
    logger.debug(f"[download-chunk] 开始下载块: lookup_code={lookup_code}, original_lookup_code={original_lookup_code}, user_id={user_id}, chunk_index={chunk_index}, session_id={session_id[:8]}...")
    
    # 首先检查下载池（使用会话独立的池）
    found_chunk = None
    used_key = None
    
    if original_lookup_code in download_pool and session_id in download_pool[original_lookup_code]:
        pool = download_pool[original_lookup_code][session_id]
        if chunk_index in pool['chunks']:
            found_chunk = pool['chunks'][chunk_index]
            used_key = original_lookup_code
            # 更新访问信息
            pool['last_access'] = datetime.now(timezone.utc)
            pool['access_count'] = pool.get('access_count', 0) + 1
            logger.debug(f"[download-chunk] ✓ 从下载池获取块: {chunk_index} (session={session_id[:8]}...)")
    
    # 如果下载池中没有，从主缓存读取
    if not found_chunk:
        # 从内存缓存读取
        # 使用原始的查找码作为键，支持多个 lookup_code 共享同一个文件块缓存
        # 首先尝试使用 original_lookup_code
        if chunk_cache.exists(original_lookup_code, user_id):
            chunks = chunk_cache.get(original_lookup_code, user_id)
            if chunk_index in chunks:
                found_chunk = chunks[chunk_index]
                used_key = original_lookup_code
                logger.debug(f"[download-chunk] ✓ 从主缓存获取块: {chunk_index}")
            else:
                logger.warning(f"[download-chunk] original_lookup_code 存在但块索引不存在: original_lookup_code={original_lookup_code}, chunk_index={chunk_index}")
        else:
            logger.warning(f"[download-chunk] 标识码不存在于缓存: original_lookup_code={original_lookup_code}, user_id={user_id}")
            # 尝试不使用用户ID（向后兼容）
            if user_id is not None:
                if chunk_cache.exists(original_lookup_code, None):
                    chunks = chunk_cache.get(original_lookup_code, None)
                    if chunk_index in chunks:
                        found_chunk = chunks[chunk_index]
                        used_key = original_lookup_code
                        logger.warning(f"[download-chunk] 使用向后兼容方式找到块: original_lookup_code={original_lookup_code}, chunk_index={chunk_index}")
    
    if not found_chunk:
        logger.error(f"[download-chunk] ✗ 文件块不存在: lookup_code={lookup_code}, original_lookup_code={original_lookup_code}, user_id={user_id}, chunk_index={chunk_index}")
        return JSONResponse(
            status_code=404,
            content=not_found_response(msg="文件块不存在或已过期")
        )
    
    chunk_info = found_chunk
    
    # 检查是否过期（使用取件码的过期时间，绝对时间）
    pickup_expire_at = chunk_info.get('pickup_expire_at') or chunk_info.get('expires_at')
    if pickup_expire_at:
        pickup_expire_at = ensure_aware_datetime(pickup_expire_at)
        now = datetime.now(timezone.utc)
        if now > pickup_expire_at:
            # 自动删除过期数据
            logger.warning(f"[download-chunk] 文件块已过期: used_key={used_key}, user_id={user_id}, chunk_index={chunk_index}, expire_at={pickup_expire_at}, now={now}")
            chunks = chunk_cache.get(used_key, user_id)
            if chunks and chunk_index in chunks:
                del chunks[chunk_index]
                chunk_cache.set(used_key, chunks, user_id)
            return JSONResponse(
                status_code=404,
                content=not_found_response(msg="文件块已过期")
            )
        else:
            logger.info(f"[download-chunk] 文件块未过期: used_key={used_key}, user_id={user_id}, chunk_index={chunk_index}, expire_at={pickup_expire_at}, now={now}")
    else:
        logger.warning(f"[download-chunk] 文件块没有过期时间: used_key={used_key}, user_id={user_id}, chunk_index={chunk_index}")
    
    # 如果从主缓存读取，初始化下载池并预读取后续块（为当前会话创建独立的池）
    if used_key:
        # 确保下载池结构存在
        if original_lookup_code not in download_pool:
            download_pool[original_lookup_code] = {}
        
        # 为当前会话创建独立的下载池（如果不存在）
        if session_id not in download_pool[original_lookup_code]:
            # 获取文件信息以确定总块数
            total_chunks = None
            if file_info_cache.exists(original_lookup_code, user_id):
                file_info = file_info_cache.get(original_lookup_code, user_id)
                total_chunks = file_info.get('totalChunks') if file_info else None
            
            if total_chunks:
                # 初始化会话独立的下载池
                download_pool[original_lookup_code][session_id] = {
                    'chunks': {},
                    'last_access': datetime.now(timezone.utc),
                    'access_count': 0,
                    'total_chunks': total_chunks,
                    'loaded_chunks': set()
                }
                logger.debug(f"[download-chunk] 初始化会话下载池: session_id={session_id[:8]}..., total_chunks={total_chunks}")
                # 异步预读取后续块（不阻塞当前请求）
                # 传递 user_id 以便正确访问文件块缓存
                import asyncio
                asyncio.create_task(preload_next_chunks(original_lookup_code, session_id, chunk_index, total_chunks, user_id=user_id))
    
    # 返回加密后的数据块（流式响应）
    chunk_data = chunk_info['data']
    logger.debug(f"[download-chunk] ✓ 准备返回文件块: used_key={used_key}, chunk_index={chunk_index}, data_length={len(chunk_data) if chunk_data else 0} 字节")
    
    return StreamingResponse(
        io.BytesIO(chunk_data),
        media_type="application/octet-stream",
        headers={
            "X-Chunk-Index": str(chunk_index),
            "X-Chunk-Hash": chunk_info['hash'],
            "X-Encrypted": "true",  # 标识数据已加密
            "Content-Disposition": f"attachment; filename=chunk_{chunk_index}.encrypted"
        }
    )


async def download_chunks_batch(
    code: str,
    request: dict,
    session_id: Optional[str],
    db: Session
):
    """
    批量下载文件块（优化性能）
    
    请求体格式:
    {
        "chunkIndices": [0, 1, 2, ...],  # 要下载的块索引列表
        "sessionId": "..."  # 可选的会话ID
    }
    
    返回格式:
    {
        "chunks": {
            "0": {"data": base64_encoded_data, "hash": "...", ...},
            "1": {"data": base64_encoded_data, "hash": "...", ...},
            ...
        },
        "missing": [5, 10],  # 缺失的块索引（如果存在）
        "expired": [3]  # 过期的块索引（如果存在）
    }
    """
    # 验证取件码
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误，必须为6位大写字母或数字")
    
    # 获取取件码
    pickup_code = get_pickup_code_by_lookup(db, code)
    if not pickup_code:
        return not_found_response(msg=f"取件码不存在")
    
    lookup_code = code
    original_lookup_code = get_original_lookup_code(lookup_code, db)
    
    # 获取要下载的块索引
    chunk_indices = request.get('chunkIndices', [])
    if not chunk_indices:
        return bad_request_response(msg="chunkIndices 不能为空")
    
    # 确保有session_id（如果没有，生成一个）
    if not session_id:
        # 如果没有session_id，生成一个（这种情况不应该发生，但为了安全）
        session_id = str(uuid.uuid4())
        if original_lookup_code not in active_download_sessions:
            active_download_sessions[original_lookup_code] = set()
        active_download_sessions[original_lookup_code].add(session_id)
        logger.warning(f"[download-chunks-batch] 生成了新的session_id: {session_id}")
    else:
        # 验证会话ID（如果提供）
        if original_lookup_code in active_download_sessions:
            if session_id not in active_download_sessions[original_lookup_code]:
                logger.warning(f"无效的下载会话ID: lookup_code={lookup_code}, session_id={session_id}")
    
    # ========== 性能优化：一次性读取整个chunks字典，避免重复反序列化 ==========
    now = datetime.now(timezone.utc)
    
    # 更新下载池访问时间并获取池中的块（使用会话独立的池）
    pool_chunks = None
    pool_data = None
    if original_lookup_code in download_pool and session_id in download_pool[original_lookup_code]:
        pool_data = download_pool[original_lookup_code][session_id]
        pool_data['last_access'] = now
        pool_chunks = pool_data.get('chunks', {})
    
    # 获取用户ID（用于缓存隔离）
    user_id = None
    try:
        from app.models.file import File
        file_record = db.query(File).filter(File.id == pickup_code.file_id).first()
        if file_record and file_record.uploader_id:
            user_id = file_record.uploader_id
    except Exception as e:
        logger.debug(f"无法获取上传者ID: {e}")
    
    # 一次性从主缓存读取整个chunks字典（只反序列化一次，而不是25次）
    # 这是最大的性能优化：避免在循环中重复访问Redis
    # 使用标识码访问缓存（所有取件码都映射到标识码）
    main_chunks_dict = None
    used_key = None
    if chunk_cache.exists(original_lookup_code, user_id):
        main_chunks_dict = chunk_cache.get(original_lookup_code, user_id)  # 只反序列化一次（如果使用Redis）
        used_key = original_lookup_code
    elif user_id is not None:
        # 向后兼容：尝试不使用用户ID
        if chunk_cache.exists(original_lookup_code, None):
            main_chunks_dict = chunk_cache.get(original_lookup_code, None)
            used_key = original_lookup_code
    
    if not main_chunks_dict and not pool_chunks:
        return bad_request_response(msg="文件块不存在")
    
    # 批量读取块
    chunks_result = {}
    missing_indices = []
    expired_indices = []
    import base64
    
    # 批量处理所有块（避免重复访问缓存）
    # 优化：先处理下载池中的块（内存操作，最快），再处理主缓存中的块
    chunks_to_add_to_pool = {}  # 记录需要添加到下载池的块
    
    for chunk_index in chunk_indices:
        found_chunk = None
        
        # 首先检查下载池（内存操作，快速）
        if pool_chunks and chunk_index in pool_chunks:
            found_chunk = pool_chunks[chunk_index]
        # 如果下载池中没有，从主缓存读取（已一次性加载）
        elif main_chunks_dict and chunk_index in main_chunks_dict:
            found_chunk = main_chunks_dict[chunk_index]
            # 记录需要添加到下载池的块（批量添加，避免重复操作）
            chunks_to_add_to_pool[chunk_index] = found_chunk
        
        if not found_chunk:
            missing_indices.append(chunk_index)
            continue
        
        # 检查是否过期（批量处理，减少重复的时区转换）
        pickup_expire_at = found_chunk.get('pickup_expire_at') or found_chunk.get('expires_at')
        if pickup_expire_at:
            pickup_expire_at = ensure_aware_datetime(pickup_expire_at)
            if now > pickup_expire_at:
                expired_indices.append(chunk_index)
                # 从缓存中删除过期块
                if used_key and main_chunks_dict and chunk_index in main_chunks_dict:
                    del main_chunks_dict[chunk_index]
                    # 更新缓存
                    chunk_cache.set(used_key, main_chunks_dict, user_id)
                if pool_chunks and chunk_index in pool_chunks:
                    del pool_chunks[chunk_index]
                continue
        
        # 将块数据编码为 base64（用于 JSON 传输）
        chunk_data = found_chunk.get('data', b'')
        chunk_result = {
            'data': base64.b64encode(chunk_data).decode('utf-8'),
            'hash': found_chunk.get('hash', ''),
            'index': chunk_index
        }
        chunks_result[str(chunk_index)] = chunk_result
    
    # 批量将块添加到下载池（优化：一次性更新，而不是逐个更新）
    # 确保下载池结构存在（为当前会话创建独立的池）
    if chunks_to_add_to_pool:
        if original_lookup_code not in download_pool:
            download_pool[original_lookup_code] = {}
        
        if session_id not in download_pool[original_lookup_code]:
            # 获取文件信息以确定总块数
            total_chunks = None
            if file_info_cache.exists(original_lookup_code, user_id):
                file_info = file_info_cache.get(original_lookup_code, user_id)
                total_chunks = file_info.get('totalChunks') if file_info else None
            
            # 初始化会话独立的下载池
            download_pool[original_lookup_code][session_id] = {
                'chunks': {},
                'last_access': now,
                'access_count': 0,
                'total_chunks': total_chunks,
                'loaded_chunks': set()
            }
            logger.debug(f"[download-chunks-batch] 初始化会话下载池: session_id={session_id[:8]}..., total_chunks={total_chunks}")
        
        pool_data = download_pool[original_lookup_code][session_id]
        pool_data['chunks'].update(chunks_to_add_to_pool)
        # 更新已加载的块索引
        if 'loaded_chunks' not in pool_data:
            pool_data['loaded_chunks'] = set()
        pool_data['loaded_chunks'].update(chunks_to_add_to_pool.keys())
    
    # 异步预读取后续块到下载池（优化：在批量下载时也触发预读取）
    if chunks_result and original_lookup_code in download_pool and session_id in download_pool[original_lookup_code]:
        pool_data = download_pool[original_lookup_code][session_id]
        total_chunks = pool_data.get('total_chunks')
        if total_chunks:
            # 获取当前批次的最大索引，预读取后续块
            max_index = max(chunk_indices) if chunk_indices else 0
            import asyncio
            asyncio.create_task(preload_next_chunks(original_lookup_code, session_id, max_index, total_chunks, preload_count=25, user_id=user_id))
    
    # 返回结果
    response_data = {
        'chunks': chunks_result
    }
    if missing_indices:
        response_data['missing'] = missing_indices
    if expired_indices:
        response_data['expired'] = expired_indices
    
    logger.debug(f"[download-chunks-batch] 批量下载完成: lookup_code={lookup_code}, 请求={len(chunk_indices)}个块, 成功={len(chunks_result)}个, 缺失={len(missing_indices)}个, 过期={len(expired_indices)}个")
    
    return success_response(data=response_data)


async def download_complete(
    code: str,
    session_id: Optional[str],
    db: Session
):
    """
    通知服务器下载完成
    
    功能：
    - 清除下载会话记录
    - 增加使用次数
    - 如果达到上限，更新状态为completed
    - 不删除文件块（可能还有其他接收者需要下载）
    """
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
    
    # 清除下载会话记录（如果提供了session_id）
    lookup_code = code
    original_lookup_code = get_original_lookup_code(lookup_code, db)
    if session_id and original_lookup_code in active_download_sessions:
        if session_id in active_download_sessions[original_lookup_code]:
            active_download_sessions[original_lookup_code].remove(session_id)
            logger.info(f"清除下载会话: lookup_code={lookup_code}, session_id={session_id}, 剩余活跃会话={len(active_download_sessions[original_lookup_code])}")
            # 如果集合为空，删除键
            if not active_download_sessions[original_lookup_code]:
                del active_download_sessions[original_lookup_code]
    
    # 清理下载池中的会话数据（如果提供了session_id）
    if session_id and original_lookup_code in download_pool:
        if session_id in download_pool[original_lookup_code]:
            del download_pool[original_lookup_code][session_id]
            logger.debug(f"清理下载池会话数据: lookup_code={lookup_code}, session_id={session_id[:8]}...")
            # 如果该lookup_code的所有会话都被清理，删除该键
            if not download_pool[original_lookup_code]:
                del download_pool[original_lookup_code]
    
    # 获取当前使用次数和限制
    used_count = pickup_code.used_count or 0
    limit_count = pickup_code.limit_count or 3
    
    # 检查是否已达到上限（999表示无限）
    if limit_count != 999 and used_count >= limit_count:
        # 已达到上限，更新状态为completed
        pickup_code.status = "completed"
        pickup_code.updated_at = datetime.now(timezone.utc)
        db.commit()
        return bad_request_response(
            msg="取件码已达到使用上限",
            data={
                "code": "LIMIT_REACHED",
                "usedCount": used_count,
                "limitCount": limit_count,
                "remaining": 0,
                "status": "completed"
            }
        )
    
    # 增加使用次数
    pickup_code.used_count = used_count + 1
    pickup_code.updated_at = datetime.now(timezone.utc)
    
    # 检查是否达到上限（增加后）
    new_used_count = pickup_code.used_count
    if limit_count != 999 and new_used_count >= limit_count:
        # 达到上限，更新状态为completed
        pickup_code.status = "completed"
    
    db.commit()
    db.refresh(pickup_code)
    
    # 注意：这里不删除文件块，因为可能还有其他接收者需要下载
    # 文件块会在过期后自动清理
    
    return success_response(
        msg="下载完成通知已接收，使用次数已更新",
        data={
            "usedCount": pickup_code.used_count,
            "limitCount": limit_count,
            "remaining": 999 if limit_count == 999 else (limit_count - pickup_code.used_count),
            "status": pickup_code.status
        }
    )