from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid
import logging
from app.utils.response import success_response, not_found_response, bad_request_response, created_response
from app.utils.validation import validate_pickup_code
from app.utils.pickup_code import generate_unique_pickup_code
from app.extensions import get_db
from app.models.pickup_code import PickupCode
from app.models.file import File
from app.schemas.request import CreateCodeRequest
from app.schemas.response import PickupCodeStatusResponse, FileInfoResponse, UsageUpdateResponse, CreateCodeResponse

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
        # 1. 生成 UUID 作为存储文件名
        stored_name = str(uuid.uuid4())
        
        # 2. 获取客户端 IP 地址
        client_ip = request.client.host if request.client else None
        # 如果通过代理，尝试从 X-Forwarded-For 获取真实 IP
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        
        # 3. 计算过期时间
        expire_hours = request_data.expireHours or 24
        expire_at = datetime.utcnow() + timedelta(hours=expire_hours)
        
        # 4. 创建数据库表 files 记录
        file_record = File(
            original_name=request_data.originalName,
            stored_name=stored_name,
            size=request_data.size,
            hash=request_data.hash,
            mime_type=request_data.mimeType
        )
        db.add(file_record)
        db.flush()  # 获取 file_id，但不提交事务
        
        # 5. 生成唯一取件码
        pickup_code = generate_unique_pickup_code(db)
        
        # 6. 创建数据库表 pickup_codes 记录
        limit_count = request_data.limitCount if request_data.limitCount else 3
        pickup_code_record = PickupCode(
            code=pickup_code,
            file_id=file_record.id,
            status="waiting",
            used_count=0,
            limit_count=limit_count,
            uploader_ip=client_ip,
            expire_at=expire_at
        )
        db.add(pickup_code_record)
        
        # 7. 提交事务
        db.commit()
        db.refresh(file_record)
        db.refresh(pickup_code_record)
        
        # 8. 构建响应数据
        response_data = CreateCodeResponse(
            code=pickup_code_record.code,
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
    - code: 6位取件码（大写字母和数字）
    
    返回：
    - 取件码信息
    - 文件信息
    - 使用状态
    """
    # 验证取件码格式
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误，必须为6位大写字母或数字")
    
    # 查询数据库
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
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


@router.get("/{code}/file-info")
async def get_file_info(code: str, db: Session = Depends(get_db)):
    """
    获取文件详细信息
    
    参数：
    - code: 6位取件码
    
    返回：
    - 文件的完整信息
    """
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    # 查询取件码和关联文件
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
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
    - code: 6位取件码
    
    返回：
    - 更新后的使用情况
    """
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
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