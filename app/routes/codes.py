from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.utils.response import success_response, not_found_response, bad_request_response
from app.utils.validation import validate_pickup_code
from app.extensions import get_db
from app.models.pickup_code import PickupCode
from app.models.file import File
from app.schemas.response import PickupCodeStatusResponse, FileInfoResponse, UsageUpdateResponse

router = APIRouter(tags=["取件码管理"], prefix="/codes")


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