from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid
import logging
from app.utils.response import success_response, not_found_response, bad_request_response, created_response
from app.utils.validation import validate_pickup_code
from app.utils.pickup_code import generate_unique_pickup_code, check_and_update_expired_pickup_code
from app.extensions import get_db
from app.models.pickup_code import PickupCode
from app.models.file import File
from app.schemas.request import CreateCodeRequest
from app.schemas.response import PickupCodeStatusResponse, FileInfoResponse, UsageUpdateResponse, CreateCodeResponse
# 导入映射表（用于支持一个文件对应多个取件码）
from app.routes.relay import lookup_code_mapping

logger = logging.getLogger(__name__)

router = APIRouter(tags=["取件码管理"], prefix="/codes")


@router.post("", status_code=201)
async def create_code(
    request_data: CreateCodeRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    创建文件元数据对象和取件码
    
    参数：
    - request_data: 文件元数据信息
    - request: FastAPI 请求对象（用于获取客户端IP）
    
    返回：
    - 创建的取件码信息
    """
    # 验证请求数据（Pydantic 会自动验证，这里只是记录日志）
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"创建取件码请求: originalName={request_data.originalName}, size={request_data.size}, "
                f"mimeType={request_data.mimeType}, limitCount={request_data.limitCount}, "
                f"expireHours={request_data.expireHours}")
    
    try:
        # 1. 检查文件是否已存在（去重逻辑）
        # 优先使用哈希，如果没有哈希则使用文件名+大小
        existing_file = None
        file_unchanged = False
        
        if request_data.hash:
            # 使用哈希查找（最准确）
            existing_file = db.query(File).filter(File.hash == request_data.hash).first()
            if existing_file:
                file_unchanged = True  # 哈希匹配，说明文件没有更改
                logger.info(f"通过哈希找到已存在的文件: file_id={existing_file.id}, hash={request_data.hash[:16]}...")
        else:
            # 如果没有哈希，使用文件名+大小查找（不够准确，但可以接受）
            # 注意：这种方式不够准确，同名同大小的不同文件会被误判
            existing_file = db.query(File).filter(
                File.original_name == request_data.originalName,
                File.size == request_data.size
            ).first()
            if existing_file:
                # 如果找到的文件有哈希，但当前请求没有哈希，无法确定是否相同
                # 为了安全，如果找到的文件有哈希，我们假设文件可能已更改，允许创建新码
                if existing_file.hash:
                    logger.info(f"找到同名同大小的文件，但无法确认是否相同（缺少哈希），允许创建新码")
                    existing_file = None  # 重置，允许创建新码
                else:
                    file_unchanged = True  # 都没有哈希，假设文件未更改
                    logger.info(f"通过文件名+大小找到已存在的文件: file_id={existing_file.id}, name={request_data.originalName}, size={request_data.size}")
        
        # 2. 如果文件已存在且未更改，检查是否有未过期的取件码
        if existing_file and file_unchanged:
            # 查找该文件关联的未过期且未完成的取件码
            existing_pickup_code = db.query(PickupCode).filter(
                PickupCode.file_id == existing_file.id,
                PickupCode.status.in_(["waiting", "transferring"]),  # 只查找等待中或传输中的
                PickupCode.expire_at > datetime.utcnow()  # 未过期
            ).order_by(PickupCode.created_at.desc()).first()  # 获取最新的
            
            if existing_pickup_code:
                # 检查并更新过期状态
                check_and_update_expired_pickup_code(existing_pickup_code, db)
                db.refresh(existing_pickup_code)
                
                # 如果仍然有效，阻止创建新码
                if existing_pickup_code.status in ["waiting", "transferring"] and existing_pickup_code.expire_at > datetime.utcnow():
                    logger.info(f"找到未过期的取件码: code={existing_pickup_code.code}, file_id={existing_file.id}")
                    return bad_request_response(
                        msg="该文件已创建过未过期的取件码，请使用已存在的取件码。如果所有取件码都已过期，可以重新生成。",
                        data={
                            "code": "FILE_ALREADY_EXISTS",
                            "fileId": existing_file.id,
                            "existingLookupCode": existing_pickup_code.code  # 只返回6位查找码
                        }
                    )
            # 如果没有未过期的取件码，允许创建新的取件码（复用文件记录）
            logger.info(f"文件已存在但所有取件码都已过期，允许创建新的取件码: file_id={existing_file.id}")
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
        expire_at = datetime.utcnow() + timedelta(hours=expire_hours)
        
        # 6. 创建或复用文件记录
        original_lookup_code = None  # 初始化变量
        if existing_file and file_unchanged:
            # 文件已存在且未更改，复用文件记录
            file_record = existing_file
            logger.info(f"复用已存在的文件记录: file_id={file_record.id}")
            # 查找该文件的第一个取件码（按创建时间排序），作为原始的 lookup_code
            original_pickup_code = db.query(PickupCode).filter(
                PickupCode.file_id == existing_file.id
            ).order_by(PickupCode.created_at.asc()).first()  # 获取最早的取件码作为原始码
            
            if original_pickup_code:
                # 记录原始 lookup_code，稍后创建映射关系
                original_lookup_code = original_pickup_code.code
                logger.info(f"找到原始取件码: {original_lookup_code}，将创建映射关系")
        else:
            # 文件不存在或已更改，创建新记录
            file_record = File(
                original_name=request_data.originalName,
                stored_name=stored_name,
                size=request_data.size,
                hash=request_data.hash,
                mime_type=request_data.mimeType
            )
            db.add(file_record)
            db.flush()  # 获取 file_id，但不提交事务
        
        # 7. 生成唯一取件码
        # 返回：(lookup_code, full_code)
        # - lookup_code: 6位查找码（存储到数据库）
        # - full_code: 12位完整取件码（返回给前端，包含后6位密钥码）
        lookup_code, full_code = generate_unique_pickup_code(db)
        
        # 8. 创建数据库表 pickup_codes 记录（只存储6位查找码）
        limit_count = request_data.limitCount if request_data.limitCount else 3
        now = datetime.utcnow()
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
        # 如果文件已存在（复用文件记录），映射到原始的 lookup_code
        # 如果文件不存在（新文件），创建自映射（键值相同）
        # 这样所有取件码都通过映射表，统一处理逻辑
        if original_lookup_code:
            # 复用文件记录：映射到原始的 lookup_code
            lookup_code_mapping[lookup_code] = original_lookup_code
            logger.info(f"创建 lookup_code 映射（复用文件）: {lookup_code} -> {original_lookup_code}")
        else:
            # 新文件：创建自映射（键值相同）
            lookup_code_mapping[lookup_code] = lookup_code
            logger.info(f"创建 lookup_code 自映射（新文件）: {lookup_code} -> {lookup_code}")
        
        # 10. 构建响应数据
        # 返回完整的12位取件码给前端（包含后6位密钥码）
        response_data = CreateCodeResponse(
            code=full_code,  # 返回12位完整码给前端
            fileId=file_record.id,
            fileName=file_record.original_name,
            fileSize=file_record.size,
            mimeType=file_record.mime_type,
            limitCount=pickup_code_record.limit_count,
            expireAt=pickup_code_record.expire_at,
            createdAt=pickup_code_record.created_at
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
    
    将文件关联的所有取件码标记为过期，并清理相关缓存
    注意：此操作不可逆
    """
    # 查询文件
    file_record = db.query(File).filter(File.id == file_id).first()
    if not file_record:
        return not_found_response(msg="文件不存在")
    
    # 查询该文件关联的所有取件码
    pickup_codes = db.query(PickupCode).filter(PickupCode.file_id == file_id).all()
    
    # 将所有取件码标记为过期
    for pickup_code in pickup_codes:
        pickup_code.status = "expired"
        pickup_code.expire_at = datetime.utcnow()  # 立即过期
    
    db.commit()
    
    logger.info(f"文件 {file_id} 已被作废，共 {len(pickup_codes)} 个取件码被标记为过期")
    
    return success_response(
        msg="文件记录已作废",
        data={
            "fileId": file_id,
            "invalidatedCodes": len(pickup_codes)
        }
    )


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
    response_data = FileInfoResponse(
        fileId=file.id,
        originalName=file.original_name,
        storedName=file.stored_name,
        size=file.size,
        hash=file.hash,
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