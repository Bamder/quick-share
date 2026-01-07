from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import uuid
import logging
from app.utils.response import success_response, not_found_response, bad_request_response, created_response
from app.utils.validation import validate_pickup_code
from app.utils.pickup_code import generate_unique_pickup_code, check_and_update_expired_pickup_code, ensure_aware_datetime, DatetimeUtil
from app.extensions import get_db
from app.models.pickup_code import PickupCode
from app.models.file import File
from app.schemas.request import CreateCodeRequest
from app.schemas.response import PickupCodeStatusResponse, FileInfoResponse, UsageUpdateResponse, CreateCodeResponse
from app.services.cache_service import chunk_cache, file_info_cache, encrypted_key_cache
from app.services.mapping_service import lookup_code_mapping
from app.utils.cache import cache_manager
# 导入映射表和缓存（用于支持一个文件对应多个取件码）
from app.services.mapping_service import lookup_code_mapping
from app.services.cache_service import encrypted_key_cache, chunk_cache, file_info_cache
# 去重指纹：从 (user_id + 明文文件哈希 + 服务器 pepper) 派生，用于后端去重与用户隔离
from app.utils.dedupe import derive_dedupe_fingerprint
# 导入认证相关功能
from app.routes.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["取件码管理"], prefix="/codes")


@router.post("", status_code=201)
async def create_code(
    request_data: CreateCodeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    创建文件元数据对象和取件码
    
    重要：此接口只能通过用户明确点击"生成取件码"按钮时调用。
    不允许在其他情况下（如文件上传完成后）自动调用此接口。
    
    参数：
    - request_data: 文件元数据信息
    - request: FastAPI 请求对象（用于获取客户端IP）
    
    返回：
    - 创建的取件码信息
    """
    # 验证请求数据（Pydantic 会自动验证，这里只是记录日志）
    import logging
    logger = logging.getLogger(__name__)
    
    # 记录取件码创建请求的来源信息（用于审计）
    client_ip = request.client.host if request.client else None
    if "x-forwarded-for" in request.headers:
        client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
    user_agent = request.headers.get("user-agent", "unknown")
    
    logger.info(f"[取件码创建] 用户操作触发: originalName={request_data.originalName}, size={request_data.size}, "
                f"mimeType={request_data.mimeType}, limitCount={request_data.limitCount}, "
                f"expireHours={request_data.expireHours}, client_ip={client_ip}, user_agent={user_agent[:50]}")
    
    try:
        # 检查权限：只有登录用户才能创建取件码
        if not current_user:
            return bad_request_response(
                msg="只有登录用户才能生成取件码",
                data={"code": "UNAUTHORIZED", "status": "unauthorized"}
            )
        
        # 1. 检查文件是否已存在（去重逻辑）
        # 获取当前用户ID（用于文件去重和缓存隔离）
        current_user_id = current_user.id if current_user else None

        # 使用文件复用服务检查文件是否存在
        from app.services.file_reuse_service import FileReuseService
        existing_file, file_unchanged = FileReuseService.check_file_exists(
            hash_value=request_data.hash,
            original_name=request_data.originalName,
            size=request_data.size,
            uploader_id=current_user_id,
            db=db
        )
        
        # 2. 如果文件已存在且未更改，检查是否有未过期的取件码
        if existing_file and file_unchanged:
            # 检查是否有未过期的取件码
            has_active_pickup_code, active_pickup_code = FileReuseService.check_active_pickup_code(
                existing_file=existing_file,
                db=db
            )

            if has_active_pickup_code and active_pickup_code:
                # 检查是否是复用文件缓存的情况
                reuse_file_cache = getattr(request_data, 'reuseFileCache', False)
                if reuse_file_cache:
                    logger.info(f"检测到复用文件缓存请求，允许创建新的取件码: file_id={existing_file.id}")
                    # 继续执行，允许复用文件记录创建新的取件码
                else:
                    # 如果不是复用缓存的情况，阻止创建新码
                    logger.info(f"找到未过期的取件码: code={active_pickup_code.code}, file_id={existing_file.id}")
                    return bad_request_response(
                        msg="该文件已创建过未过期的取件码，请使用已存在的取件码。如果所有取件码都已过期，可以重新生成。",
                        data={
                            "code": "FILE_ALREADY_EXISTS",
                            "fileId": existing_file.id,
                            "existingLookupCode": active_pickup_code.code,  # 只返回6位查找码
                            "hasCachedChunks": True,  # 有未过期的取件码，缓存应该存在
                            "hasCachedKey": True  # 有未过期的取件码，密钥应该存在
                        }
                    )
            
            # 如果没有未过期的取件码，检查是否有可复用的文件块缓存
            # 获取原始上传者的 user_id（文件块缓存是用这个 user_id 存储的）
            original_uploader_id = existing_file.uploader_id if existing_file else None
            
            # 查找该文件的所有取件码，检查哪个取件码对应的缓存存在
            # 优化：只查询 code 字段，提高性能
            # 只查询活跃状态的取件码，避免使用已过期的取件码
            all_pickup_codes = db.query(PickupCode.code).filter(
                PickupCode.file_id == existing_file.id,
                PickupCode.status.in_(["waiting", "transferring"])  # 只查询活跃状态
            ).all()
            
            # 找到第一个有缓存的取件码，并通过标识码查找缓存
            # 先检查临时池，再检查主缓存
            original_lookup_code = None
            from app.services.pool_service import upload_pool
            from app.services.mapping_service import get_identifier_code
            
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
                if original_uploader_id is not None and chunk_cache.exists(test_identifier_code, original_uploader_id):
                    original_lookup_code = test_lookup_code
                    logger.info(f"✓ 在主缓存找到缓存: lookup_code={test_lookup_code}, identifier_code={test_identifier_code}")
                    break
                elif original_uploader_id is None and chunk_cache.exists(test_identifier_code, None):
                    original_lookup_code = test_lookup_code
                    logger.info(f"✓ 在主缓存找到缓存（匿名用户）: lookup_code={test_lookup_code}, identifier_code={test_identifier_code}")
                    break
            
            # 如果没找到有缓存的取件码，使用最早的取件码作为原始码
            if not original_lookup_code:
                # 查询最早的活跃取件码（按创建时间排序，只查未过期状态）
                earliest_pickup_code = db.query(PickupCode.code).filter(
                    PickupCode.file_id == existing_file.id,
                    PickupCode.status.in_(["waiting", "transferring"])
                ).order_by(PickupCode.created_at.asc()).first()
                if earliest_pickup_code:
                    original_lookup_code = earliest_pickup_code.code
                    logger.info(f"未找到有缓存的取件码，使用最早的取件码: lookup_code={original_lookup_code}")

            # 检查是否所有取件码都已过期（status == "expired"）
            # 注意：这里只检查 status == "expired"，不检查 expire_at，因为用户可能手动作废了取件码
            # 优化：使用 exists() 而不是 count()，只判断是否存在，不计数
            from sqlalchemy import exists
            all_expired = not db.query(exists().where(
                PickupCode.file_id == existing_file.id,
                PickupCode.status != "expired"
            )).scalar()
            
            # 无论取件码是否过期，都应该检查缓存，如果存在就提示用户是否可以复用
            # 注意：文件块是加密的，需要检查文件块缓存是否存在且未过期
            # 文件信息缓存是在 upload_complete 时存储的，但即使文件信息缓存不存在，文件块缓存也可能存在
            has_file_info = False
            has_chunks = False
            chunks_expired = True
            chunks = None
            
            # 重要：文件缓存应该与上传用户强绑定
            # 只有在文件哈希相同且上传用户也相同时，才认为是完全同一个文件
            # 因此，使用原始上传者的 user_id 查找缓存（缓存是用原始上传者的 user_id 存储的）
            
            # 使用标识码查找文件缓存（标识码与文件缓存强绑定）
            # 先通过映射服务获取标识码，然后用标识码查找文件信息缓存
            identifier_code = None
            if original_lookup_code:
                try:
                    # 优先从映射服务获取标识码（这是最可靠的方式）
                    from app.services.mapping_service import get_identifier_code
                    identifier_code = get_identifier_code(original_lookup_code, db, "reuse_file_check")
                    if identifier_code:
                        logger.info(f"从映射服务获取标识码: original_lookup_code={original_lookup_code} -> identifier_code={identifier_code}")
                    
                    # 如果映射服务没有，尝试从文件信息缓存获取（向后兼容）
                    # 注意：文件信息缓存是用标识码作为键存储的，所以如果 original_lookup_code 就是标识码，可以直接查找
                    if not identifier_code:
                        if original_uploader_id is not None and file_info_cache.exists(original_lookup_code, original_uploader_id):
                            fi = file_info_cache.get(original_lookup_code, original_uploader_id) or {}
                            identifier_code = fi.get('identifier_code') or original_lookup_code
                            if identifier_code:
                                logger.info(f"从文件信息缓存中解析标识码: {original_lookup_code} -> identifier_code={identifier_code}")
                        elif original_uploader_id is None and file_info_cache.exists(original_lookup_code, None):
                            fi = file_info_cache.get(original_lookup_code, None) or {}
                            identifier_code = fi.get('identifier_code') or original_lookup_code
                            if identifier_code:
                                logger.info(f"从文件信息缓存中解析标识码（匿名）: {original_lookup_code} -> identifier_code={identifier_code}")
                except Exception as e:
                    logger.warning(f"获取标识码失败: {e}")
            
            # 使用标识码查找缓存（标识码必须存在，如果没有则说明是新文件）
            cache_lookup_code = identifier_code if identifier_code else original_lookup_code
            
            logger.info(f"开始检查缓存: original_lookup_code={original_lookup_code}, identifier_code={identifier_code}, cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id}, all_expired={all_expired}")
            
            # 检查文件块缓存和密钥缓存时，使用标识码
            lookup_codes_to_check = [cache_lookup_code]
            
            # 首先检查文件信息缓存是否存在（表示文件上传已完成）
            # 使用原始上传者的 user_id 查找缓存（因为缓存是用这个 user_id 存储的）
            if original_uploader_id is not None and file_info_cache.exists(cache_lookup_code, original_uploader_id):
                has_file_info = True
                logger.info(f"✓ 找到文件信息缓存: cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id}")
            elif original_uploader_id is None and file_info_cache.exists(cache_lookup_code, None):
                has_file_info = True
                logger.info(f"✓ 找到文件信息缓存（匿名用户）: cache_lookup_code={cache_lookup_code}")
            
            if not has_file_info:
                logger.info(f"✗ 文件信息缓存不存在: cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id}")
            
            # 检查文件块缓存是否存在且未过期（不依赖文件信息缓存）
            # 即使文件信息缓存不存在，文件块缓存也可能存在
            # 注意：刚上传完成的文件块可能还在临时池（upload_pool）中，需要同时检查临时池和主缓存
            from app.services.pool_service import upload_pool
            
            # 先检查临时池（upload_pool）- 使用标识码
            if cache_lookup_code in upload_pool:
                upload_pool_chunks = upload_pool[cache_lookup_code]
                if upload_pool_chunks:
                    chunks = upload_pool_chunks
                    logger.info(f"✓ 找到文件块在临时池: cache_lookup_code={cache_lookup_code}, chunks_count={len(chunks)}")
            
            # 再检查主缓存（chunk_cache）- 使用标识码
            if not chunks:
                if original_uploader_id is not None and chunk_cache.exists(cache_lookup_code, original_uploader_id):
                    chunks = chunk_cache.get(cache_lookup_code, original_uploader_id)
                    logger.info(f"✓ 找到文件块缓存: cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id}, chunks_count={len(chunks) if chunks else 0}")
                elif original_uploader_id is None and chunk_cache.exists(cache_lookup_code, None):
                    chunks = chunk_cache.get(cache_lookup_code, None)
                    logger.info(f"✓ 找到文件块缓存（匿名用户）: cache_lookup_code={cache_lookup_code}, chunks_count={len(chunks) if chunks else 0}")
            
            if not chunks:
                logger.info(f"✗ 文件块缓存不存在: cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id}")
            
            if chunks:
                # 检查第一个块的过期时间
                first_chunk = next(iter(chunks.values()))
                pickup_expire_at = first_chunk.get('pickup_expire_at') or first_chunk.get('expires_at')
                if pickup_expire_at:
                    pickup_expire_at = ensure_aware_datetime(pickup_expire_at)
                    if now < pickup_expire_at:
                        has_chunks = True
                        chunks_expired = False
                        logger.info(f"✓ 文件块缓存未过期: expire_at={pickup_expire_at}, file_id={existing_file.id}")
                    else:
                        logger.info(f"✗ 文件块缓存已过期: expire_at={pickup_expire_at}, now={now}")
                else:
                    logger.warning(f"⚠ 文件块缓存没有过期时间")
            
            # 检查密钥缓存是否存在（使用原始取件码，因为密钥缓存按取件码独立存储）
            # 注意：密钥缓存按取件码独立存储，所以检查原始取件码即可
            has_key = False
            if original_uploader_id is not None and encrypted_key_cache.exists(original_lookup_code, original_uploader_id):
                has_key = True
                logger.info(f"✓ 找到密钥缓存: original_lookup_code={original_lookup_code}, original_uploader_id={original_uploader_id}")
            elif original_uploader_id is None and encrypted_key_cache.exists(original_lookup_code, None):
                has_key = True
                logger.info(f"✓ 找到密钥缓存（匿名用户）: original_lookup_code={original_lookup_code}")
            
            if not has_key:
                logger.info(f"✗ 密钥缓存不存在: original_lookup_code={original_lookup_code}, original_uploader_id={original_uploader_id}")
                
                # 如果文件块缓存存在且未过期，提示用户是否要复用（无论取件码是否过期）
                if has_chunks and not chunks_expired:
                    logger.info(f"✓✓✓ 检测到可复用的文件块缓存，提示用户: cache_lookup_code={cache_lookup_code}, identifier_code={identifier_code}, has_key={has_key}, file_id={existing_file.id}, all_expired={all_expired}")
                    return bad_request_response(
                        msg="该文件已存在未过期的文件块缓存，可以复用。如果所有取件码都已过期，可以重新生成。",
                        data={
                            "code": "FILE_ALREADY_EXISTS",
                            "fileId": existing_file.id,
                            "existingLookupCode": cache_lookup_code,  # 返回标识码（如果存在）或原始取件码
                            "identifierCode": identifier_code,  # 返回标识码（用于前端存储）
                            "hasCachedChunks": True,  # 标记有可复用的文件块
                            "hasCachedKey": has_key  # 标记是否有密钥缓存
                        }
                    )
            
            # 如果没有未过期的取件码，也没有可复用的文件块缓存，允许创建新的取件码（复用文件记录）
            logger.info(f"文件已存在但所有取件码都已过期且没有可复用的文件块缓存，允许创建新的取件码: file_id={existing_file.id}")
            # 继续执行，使用已存在的文件记录，只创建新的取件码
        
        # 3. 如果文件已存在但哈希不同，说明文件已更改，创建新记录
        # 如果文件不存在，创建新记录
        # 如果文件已存在但所有取件码都过期，复用文件记录，只创建新的取件码
        # 生成 UUID 作为存储文件名
        stored_name = str(uuid.uuid4())
        
        # 4. 获取客户端 IP 地址
        client_ip = request.client.host if request.client else None
        # 如果通过代理，尝试从 X-Forwarded-For 获取真实 IP
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        
        # 5. 计算过期时间
        expire_hours = request_data.expireHours or 24
        expire_at = DatetimeUtil.add_hours(DatetimeUtil.now(), expire_hours)
        
        # 6. 创建或复用文件记录
        original_lookup_code = None  # 初始化变量
        should_create_new_file = False  # 标志：是否需要创建新文件记录
        
        if existing_file and file_unchanged:
            # 文件已存在且未更改，尝试复用文件记录
            # 重要：确保用户匹配（文件缓存应该与上传用户强绑定）
            # 只有在文件哈希相同且上传用户也相同时，才认为是完全同一个文件
            if current_user_id is not None and existing_file.uploader_id != current_user_id:
                # 用户不匹配，不允许复用其他用户的文件记录
                logger.warning(f"文件已存在但上传用户不同（file.uploader_id={existing_file.uploader_id}, current_user_id={current_user_id}），不允许复用文件记录")
                existing_file = None  # 重置，强制创建新文件记录
                file_unchanged = False
            else:
                # 用户匹配，可以复用文件记录
                # 优先查找未过期的取件码（按创建时间排序），如果找不到，再查找已过期的
                # 这样可以优先复用未过期的文件块和密钥缓存
                now = DatetimeUtil.now()
                
                # 先查找未过期的取件码（在Python中检查，确保时区一致性）
                all_pickup_codes = db.query(PickupCode).filter(
                    PickupCode.file_id == existing_file.id,
                    PickupCode.status.in_(["waiting", "transferring"])
                ).order_by(PickupCode.created_at.asc()).all()

                original_pickup_code = None
                for code in all_pickup_codes:
                    if code.expire_at:
                        code_expire_at = ensure_aware_datetime(code.expire_at)
                        if code_expire_at > now:
                            original_pickup_code = code
                            break
                
                # 如果找不到未过期的，不再查找已过期的（避免标识码重建失败）
                # 已过期的取件码不应该被复用
                if not original_pickup_code:
                    logger.info(f"文件 {existing_file.id} 没有活跃的取件码，跳过缓存复用检查")
                    original_pickup_code = None
                
                if original_pickup_code:
                    # 记录原始 lookup_code，检查密钥缓存和文件块缓存是否存在
                    original_lookup_code = original_pickup_code.code
                    logger.info(f"找到原始取件码: {original_lookup_code}，检查密钥缓存和文件块缓存是否存在...")
                    
                    # 获取原始上传者的 user_id（文件块缓存是用这个 user_id 存储的）
                    original_uploader_id = existing_file.uploader_id if existing_file else None
                    
                    # 优先使用标识码查找文件块缓存（标识码与文件缓存强绑定）
                    identifier_code = None
                    try:
                        if original_uploader_id is not None and file_info_cache.exists(original_lookup_code, original_uploader_id):
                            fi = file_info_cache.get(original_lookup_code, original_uploader_id) or {}
                            identifier_code = fi.get('identifier_code')
                        elif original_uploader_id is None and file_info_cache.exists(original_lookup_code, None):
                            fi = file_info_cache.get(original_lookup_code, None) or {}
                            identifier_code = fi.get('identifier_code')
                    except Exception:
                        pass
                    
                    # 如果没有从文件信息缓存获取到，从映射服务获取
                    if not identifier_code:
                        try:
                            from app.services.mapping_service import get_identifier_code
                            identifier_code = get_identifier_code(original_lookup_code, db, "reuse_cache_check")
                        except Exception:
                            pass
                    
                    # 使用标识码查找缓存（标识码机制：标识码不存在则缓存不存在）
                    if not identifier_code:
                        logger.info(f"标识码不存在（所有取件码已过期），无法复用文件记录: original_lookup_code={original_lookup_code}")
                        # 标识码不存在，所有缓存都不应该存在，直接创建新文件记录
                        should_create_new_file = True
                        original_lookup_code = None
                    elif original_uploader_id is not None:
                        # 只有在有上传者ID的情况下才进行缓存检查
                        cache_lookup_code = identifier_code
                        logger.info(f"复用文件缓存检查: original_lookup_code={original_lookup_code}, identifier_code={identifier_code}, cache_lookup_code={cache_lookup_code}")

                        # 检查文件块缓存是否存在且未过期
                        # 注意：刚上传完成的文件块可能还在临时池（upload_pool）中，需要同时检查临时池和主缓存
                        # 使用原始上传者的 user_id 查找缓存（因为缓存是用这个 user_id 存储的）
                        has_chunks = False
                        chunks_expired = True
                        chunks = None
                        from app.services.pool_service import upload_pool

                        # 先检查临时池（upload_pool）- 使用标识码
                        if cache_lookup_code in upload_pool:
                            upload_pool_chunks = upload_pool[cache_lookup_code]
                            if upload_pool_chunks:
                                chunks = upload_pool_chunks
                                logger.info(f"标识码 {cache_lookup_code} 的文件块在临时池中 (original_uploader_id={original_uploader_id}, chunks_count={len(chunks)})")

                        # 再检查主缓存（chunk_cache）- 使用标识码
                        if not chunks:
                            if chunk_cache.exists(cache_lookup_code, original_uploader_id):
                                chunks = chunk_cache.get(cache_lookup_code, original_uploader_id)
                                if chunks:
                                    logger.info(f"通过标识码 {cache_lookup_code} 找到文件块在主缓存中 (original_uploader_id={original_uploader_id}, chunks_count={len(chunks)})")

                        if chunks:
                            # 检查第一个块的过期时间
                            first_chunk = next(iter(chunks.values()))
                            pickup_expire_at = first_chunk.get('pickup_expire_at') or first_chunk.get('expires_at')
                            if pickup_expire_at:
                                pickup_expire_at = ensure_aware_datetime(pickup_expire_at)
                                if now < pickup_expire_at:
                                    has_chunks = True
                                    chunks_expired = False
                                    logger.info(f"文件块缓存存在且未过期 (cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id})")
                                else:
                                    logger.warning(f"文件块缓存已过期 (cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id})")
                            else:
                                # 临时池中的块可能没有过期时间，默认认为未过期
                                has_chunks = True
                                chunks_expired = False
                                logger.info(f"文件块缓存存在但无过期时间，默认认为未过期 (cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id})")
                        else:
                            logger.warning(f"文件块缓存不存在 (cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id})")

                        # 检查密钥缓存是否存在（使用原始上传者的 user_id）
                        # 密钥缓存按取件码独立存储，所以检查原始取件码即可
                        has_key = encrypted_key_cache.exists(original_lookup_code, original_uploader_id)
                        if has_key:
                            logger.info(f"原始取件码 {original_lookup_code} 的密钥缓存存在 (original_uploader_id={original_uploader_id})")
                        else:
                            logger.warning(f"原始取件码 {original_lookup_code} 的密钥缓存不存在 (original_uploader_id={original_uploader_id})")

                        # 如果文件块缓存存在且未过期，可以复用文件记录（即使密钥缓存不存在，也可以重新上传密钥）
                        # 如果密钥缓存存在，也可以复用文件记录
                        if has_chunks and not chunks_expired:
                            logger.info(f"文件块缓存存在且未过期（通过标识码 {cache_lookup_code}），可以复用文件记录")
                            # 复用文件记录
                            file_record = existing_file
                            # 更新文件的分享者信息（如果当前用户不同）
                            if current_user and file_record.uploader_id != current_user.id:
                                file_record.uploader_id = current_user.id
                                db.flush()
                            # 使用标识码作为 original_lookup_code（用于后续映射）
                            original_lookup_code = cache_lookup_code
                            logger.info(f"复用已存在的文件记录: file_id={file_record.id}, uploader_id={file_record.uploader_id}, identifier_code={identifier_code}, has_key={has_key}, has_chunks={has_chunks}")
                        elif has_key:
                            logger.info(f"原始取件码 {original_lookup_code} 的密钥缓存存在，可以复用文件记录")
                            # 复用文件记录
                            file_record = existing_file
                            # 更新文件的分享者信息（如果当前用户不同）
                            if current_user and file_record.uploader_id != current_user.id:
                                file_record.uploader_id = current_user.id
                                db.flush()
                            logger.info(f"复用已存在的文件记录: file_id={file_record.id}, uploader_id={file_record.uploader_id}, has_key={has_key}, has_chunks={has_chunks}")
                        else:
                            logger.warning(f"原始取件码 {original_lookup_code} 的密钥缓存和文件块缓存都不存在或已过期，无法复用文件记录，将创建新文件记录")
                            # 设置标志，强制创建新文件记录
                            should_create_new_file = True
                            original_lookup_code = None
                    else:
                        # 匿名用户，跳过缓存检查，直接创建新文件记录
                        logger.info(f"匿名用户无法复用缓存，直接创建新文件记录")
                        should_create_new_file = True
                        original_lookup_code = None
                        cache_lookup_code = identifier_code
                        logger.info(f"复用文件缓存检查: original_lookup_code={original_lookup_code}, identifier_code={identifier_code}, cache_lookup_code={cache_lookup_code}")

                        # 检查文件块缓存是否存在且未过期
                        # 注意：刚上传完成的文件块可能还在临时池（upload_pool）中，需要同时检查临时池和主缓存
                        # 使用原始上传者的 user_id 查找缓存（因为缓存是用这个 user_id 存储的）
                        has_chunks = False
                        chunks_expired = True
                        chunks = None
                        from app.services.pool_service import upload_pool

                        # 先检查临时池（upload_pool）- 使用标识码
                        if cache_lookup_code in upload_pool:
                            upload_pool_chunks = upload_pool[cache_lookup_code]
                            if upload_pool_chunks:
                                chunks = upload_pool_chunks
                                logger.info(f"标识码 {cache_lookup_code} 的文件块在临时池中 (original_uploader_id={original_uploader_id}, chunks_count={len(chunks)})")

                        # 再检查主缓存（chunk_cache）- 使用标识码
                        if not chunks:
                            if chunk_cache.exists(cache_lookup_code, original_uploader_id):
                                chunks = chunk_cache.get(cache_lookup_code, original_uploader_id)
                                if chunks:
                                    logger.info(f"通过标识码 {cache_lookup_code} 找到文件块在主缓存中 (original_uploader_id={original_uploader_id}, chunks_count={len(chunks)})")

                        if chunks:
                            # 检查第一个块的过期时间
                            first_chunk = next(iter(chunks.values()))
                            pickup_expire_at = first_chunk.get('pickup_expire_at') or first_chunk.get('expires_at')
                            if pickup_expire_at:
                                pickup_expire_at = ensure_aware_datetime(pickup_expire_at)
                                if now < pickup_expire_at:
                                    has_chunks = True
                                    chunks_expired = False
                                    logger.info(f"文件块缓存存在且未过期 (cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id})")
                                else:
                                    logger.warning(f"文件块缓存已过期 (cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id})")
                            else:
                                # 临时池中的块可能没有过期时间，默认认为未过期
                                has_chunks = True
                                chunks_expired = False
                                logger.info(f"文件块缓存存在但无过期时间，默认认为未过期 (cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id})")
                        else:
                            logger.warning(f"文件块缓存不存在 (cache_lookup_code={cache_lookup_code}, original_uploader_id={original_uploader_id})")

                        # 检查密钥缓存是否存在（使用原始上传者的 user_id）
                        # 密钥缓存按取件码独立存储，所以检查原始取件码即可
                        has_key = encrypted_key_cache.exists(original_lookup_code, original_uploader_id)
                        if has_key:
                            logger.info(f"原始取件码 {original_lookup_code} 的密钥缓存存在 (original_uploader_id={original_uploader_id})")
                        else:
                            logger.warning(f"原始取件码 {original_lookup_code} 的密钥缓存不存在 (original_uploader_id={original_uploader_id})")
                    
                    # 如果文件块缓存存在且未过期，可以复用文件记录（即使密钥缓存不存在，也可以重新上传密钥）
                    # 如果密钥缓存存在，也可以复用文件记录
                    if has_chunks and not chunks_expired:
                        logger.info(f"文件块缓存存在且未过期（通过标识码 {cache_lookup_code}），可以复用文件记录")
                        # 复用文件记录
                        file_record = existing_file
                        # 更新文件的分享者信息（如果当前用户不同）
                        if current_user and file_record.uploader_id != current_user.id:
                            file_record.uploader_id = current_user.id
                            db.flush()
                        # 使用标识码作为 original_lookup_code（用于后续映射）
                        original_lookup_code = cache_lookup_code
                        logger.info(f"复用已存在的文件记录: file_id={file_record.id}, uploader_id={file_record.uploader_id}, identifier_code={identifier_code}, has_key={has_key}, has_chunks={has_chunks}")
                    elif has_key:
                        logger.info(f"原始取件码 {original_lookup_code} 的密钥缓存存在，可以复用文件记录")
                        # 复用文件记录
                        file_record = existing_file
                        # 更新文件的分享者信息（如果当前用户不同）
                        if current_user and file_record.uploader_id != current_user.id:
                            file_record.uploader_id = current_user.id
                            db.flush()
                        logger.info(f"复用已存在的文件记录: file_id={file_record.id}, uploader_id={file_record.uploader_id}, has_key={has_key}, has_chunks={has_chunks}")
                    else:
                        logger.warning(f"原始取件码 {original_lookup_code} 的密钥缓存和文件块缓存都不存在或已过期，无法复用文件记录，将创建新文件记录")
                        # 设置标志，强制创建新文件记录
                        should_create_new_file = True
                        original_lookup_code = None
        
        # 如果需要创建新文件记录（文件不存在、已更改、或密钥缓存不存在）
        if not (existing_file and file_unchanged and not should_create_new_file):
            # 创建新记录
            # 注意：如果 request_data.hash 存在，这里会把"去重指纹"写入 File.hash（而不是明文哈希）
            stored_hash = None
            if request_data.hash:
                stored_hash = derive_dedupe_fingerprint(
                    user_id=current_user_id,
                    plaintext_file_hash=request_data.hash.strip().lower(),
                )
            file_record = File(
                original_name=request_data.originalName,
                stored_name=stored_name,
                size=request_data.size,
                hash=stored_hash,
                mime_type=request_data.mimeType,
                uploader_id=current_user.id if current_user else None  # 记录分享者账号
            )
            db.add(file_record)
            db.flush()  # 获取 file_id，但不提交事务
        else:
            # 复用已有文件记录
            file_record = existing_file
            logger.info(f"复用已有文件记录: file_id={file_record.id}, original_name={file_record.original_name}")
        
        # 7. 生成唯一取件码
        # 返回：(lookup_code, full_code)
        # - lookup_code: 6位查找码（存储到数据库）
        # - full_code: 12位完整取件码（返回给前端，包含后6位密钥码）
        lookup_code, full_code = generate_unique_pickup_code(db)
        
        # 8. 创建数据库表 pickup_codes 记录（只存储6位查找码）
        limit_count = request_data.limitCount if request_data.limitCount else 3
        now = DatetimeUtil.now()
        pickup_code_record = PickupCode(
            code=lookup_code,  # 只存储6位查找码，不存储后6位密钥码
            file_id=file_record.id,
            status="waiting",
            used_count=0,
            limit_count=limit_count,
            uploader_ip=client_ip,
            expire_at=expire_at,
            created_at=now,
            updated_at=now
        )
        db.add(pickup_code_record)
        
        # 9. 提交事务
        db.commit()
        db.refresh(file_record)
        db.refresh(pickup_code_record)
        
        # 9.5. 创建 lookup_code 映射关系
        # 如果文件已存在（复用文件记录），映射到标识码（identifier_code）
        # 如果文件不存在（新文件），创建自映射（键值相同），此时 lookup_code 就是标识码
        # 这样所有取件码都通过映射表，统一处理逻辑
        # 导入映射保存函数
        from app.services.mapping_service import save_lookup_mapping

        # 从pickup_code_record获取expire_at，确保expire_at总是被定义
        expire_at = None
        if pickup_code_record and pickup_code_record.expire_at:
            expire_at = ensure_aware_datetime(pickup_code_record.expire_at)
        
        # 确定标识码：如果文件已存在，使用标识码；如果新文件，当前 lookup_code 就是标识码
        final_identifier_code = None

        # 检查是否是复用文件缓存的情况
        reuse_file_cache = getattr(request_data, 'reuseFileCache', False)
        if reuse_file_cache:
            # 复用文件缓存：直接使用前端提供的标识码
            final_identifier_code = getattr(request_data, 'identifierCode', None)
            if final_identifier_code:
                logger.info(f"复用文件缓存，使用前端提供的标识码: {final_identifier_code}")
            else:
                logger.warning("复用文件缓存但未提供标识码，将使用默认逻辑")

        if original_lookup_code and not final_identifier_code:
            # 复用文件记录：从文件信息缓存或映射服务获取标识码
            try:
                # 优先从文件信息缓存获取标识码
                if original_uploader_id is not None and file_info_cache.exists(original_lookup_code, original_uploader_id):
                    fi = file_info_cache.get(original_lookup_code, original_uploader_id) or {}
                    final_identifier_code = fi.get('identifier_code')
                elif original_uploader_id is None and file_info_cache.exists(original_lookup_code, None):
                    fi = file_info_cache.get(original_lookup_code, None) or {}
                    final_identifier_code = fi.get('identifier_code')
                
                # 如果文件信息缓存中没有，从映射服务获取
                if not final_identifier_code:
                    from app.services.mapping_service import get_identifier_code
                    final_identifier_code = get_identifier_code(original_lookup_code, db, "create_mapping")
            except Exception as e:
                logger.warning(f"获取标识码失败: {e}")
            
            # 标识码必须存在（复用文件时）
            if not final_identifier_code:
                logger.error(f"复用文件记录时无法获取标识码: original_lookup_code={original_lookup_code}")
                final_identifier_code = original_lookup_code  # 降级：使用原始取件码作为标识码
            
            # 映射到标识码
            save_lookup_mapping(lookup_code, final_identifier_code, expire_at)
            logger.info(f"创建 lookup_code 映射（复用文件）: {lookup_code} -> {final_identifier_code} (identifier_code)")
        else:
            # 新文件：当前 lookup_code 就是标识码，创建自映射（键值相同）
            # 注意：自映射不需要保存到Redis（因为可以直接使用lookup_code本身）
            lookup_code_mapping[lookup_code] = lookup_code
            final_identifier_code = lookup_code
            logger.info(f"创建 lookup_code 自映射（新文件）: {lookup_code} -> {lookup_code} (identifier_code)")
        
        # 10. 构建响应数据
        # 返回完整的12位取件码给前端（包含后6位密钥码）
        # 同时返回标识码，供前端存储
        response_data = CreateCodeResponse(
            code=full_code,  # 返回12位完整码给前端
            fileId=file_record.id,
            fileName=file_record.original_name,
            fileSize=file_record.size,
            mimeType=file_record.mime_type,
            limitCount=pickup_code_record.limit_count,
            expireAt=pickup_code_record.expire_at,
            createdAt=pickup_code_record.created_at,
            identifierCode=final_identifier_code  # 返回标识码，供前端存储
        )
        
        return created_response(
            msg="取件码创建成功",
            data=response_data
        )
        
    except RuntimeError as e:
        # 取件码生成失败
        db.rollback()
        return bad_request_response(msg=str(e))
    except Exception as e:
        # 其他错误
        db.rollback()
        return bad_request_response(msg=f"创建取件码失败: {str(e)}")


@router.get("/{code}/status")
async def get_code_status(code: str, db: Session = Depends(get_db)):
    """
    查询取件码状态
    
    参数：
    - code: 12位取件码（前6位查找码+后6位密钥码，大写字母和数字）
    
    返回：
    - 取件码信息
    - 文件信息
    - 使用状态
    """
    # 验证取件码格式（服务器只接收6位查找码）
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误，必须为6位大写字母或数字")
    
    # 直接使用6位查找码查询数据库（服务器只接收查找码，不接触密钥码）
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码不存在")
    
    # 检查并更新过期状态
    check_and_update_expired_pickup_code(pickup_code, db)
    db.refresh(pickup_code)  # 刷新以获取最新状态
    
    # 查询关联的文件信息
    file = db.query(File).filter(File.id == pickup_code.file_id).first()
    if not file:
        return not_found_response(msg="关联的文件不存在")
    
    # 构建响应数据
    response_data = PickupCodeStatusResponse(
        code=pickup_code.code,
        fileId=file.id,
        fileName=file.original_name,
        fileSize=file.size,
        mimeType=file.mime_type,
        status=pickup_code.status or "waiting",
        usedCount=pickup_code.used_count or 0,
        limitCount=pickup_code.limit_count or 3,
        expireAt=pickup_code.expire_at,
        createdAt=pickup_code.created_at
    )
    
    return success_response(data=response_data)


@router.post("/files/{file_id}/invalidate")
async def invalidate_file(
    file_id: int,
    db: Session = Depends(get_db)
):
    """
    作废文件记录

    将文件关联的所有取件码标记为过期，并清理所有相关缓存
    注意：此操作不可逆
    """
    from app.services.file_management_service import FileManagementService
    return await FileManagementService.invalidate_file(file_id, db)


@router.get("/{code}/file-info")
async def get_file_info(code: str, db: Session = Depends(get_db)):
    """
    获取文件详细信息
    
    参数：
    - code: 12位取件码（前6位查找码+后6位密钥码）
    
    返回：
    - 文件的完整信息
    """
    # 验证取件码格式（服务器只接收6位查找码）
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误，必须为6位大写字母或数字")
    
    # 直接使用6位查找码查询数据库（服务器只接收查找码，不接触密钥码）
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码不存在")
    
    file = db.query(File).filter(File.id == pickup_code.file_id).first()
    if not file:
        return not_found_response(msg="关联的文件不存在")
    
    # 构建响应
    # 注意：File.hash 字段现在存的是“去重指纹（dedupe fingerprint）”，不是明文文件哈希。
    # 为避免误导客户端，这里不返回 hash（置为 None）。
    response_data = FileInfoResponse(
        fileId=file.id,
        originalName=file.original_name,
        storedName=file.stored_name,
        size=file.size,
        hash=None,
        mimeType=file.mime_type,
        createdAt=file.created_at
    )
    
    return success_response(data=response_data)


@router.post("/{code}/usage")
async def increment_usage(code: str, db: Session = Depends(get_db)):
    """
    增加使用次数
    
    参数：
    - code: 12位取件码（前6位查找码+后6位密钥码）
    
    返回：
    - 更新后的使用情况
    """
    # 验证取件码格式（服务器只接收6位查找码）
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误，必须为6位大写字母或数字")
    
    # 直接使用6位查找码查询数据库（服务器只接收查找码，不接触密钥码）
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码不存在")
    
    # 检查是否已达到上限
    used_count = pickup_code.used_count or 0
    limit_count = pickup_code.limit_count or 3
    
    if used_count >= limit_count:
        return bad_request_response(
            msg="已达到使用上限",
            data={
                "code": code,
                "usedCount": used_count,
                "limitCount": limit_count,
                "remaining": 0
            }
        )
    
    # 增加使用次数
    pickup_code.used_count = used_count + 1
    db.commit()
    db.refresh(pickup_code)
    
    # 构建响应
    response_data = UsageUpdateResponse(
        code=pickup_code.code,
        usedCount=pickup_code.used_count,
        limitCount=pickup_code.limit_count,
        remaining=pickup_code.limit_count - pickup_code.used_count,
        updatedAt=pickup_code.updated_at
    )
    
    return success_response(msg="使用次数已更新", data=response_data)

