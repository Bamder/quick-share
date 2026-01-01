"""
服务器中转模式API
使用端到端加密，服务器无法查看文件内容
"""

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
import hashlib
import io

from app.utils.response import (
    success_response, created_response,
    not_found_response, bad_request_response
)
from app.utils.validation import validate_pickup_code
from app.utils.pickup_code import check_and_update_expired_pickup_code
from app.extensions import get_db
from app.models.pickup_code import PickupCode

router = APIRouter(tags=["服务器中转"], prefix="/relay")


class UploadCompleteRequest(BaseModel):
    """上传完成请求模型"""
    totalChunks: int
    fileSize: int
    fileName: str
    mimeType: str


# 临时内存存储（生产环境应使用Redis）
# 格式: {code: {chunk_index: {data: bytes, hash: str, created_at: datetime, expires_at: datetime}}}
chunk_cache = {}

# 文件信息缓存（格式: {code: {fileName, fileSize, mimeType, totalChunks, uploadedAt}}）
file_info_cache = {}

# 加密密钥缓存（格式: {code: encryptedKeyBase64}）
# 注意：存储的是用取件码加密后的密钥，服务器无法直接获取原始密钥
encrypted_key_cache = {}


def cleanup_expired_chunks():
    """清理过期的文件块"""
    now = datetime.utcnow()
    expired_codes = []
    
    for code, chunks in chunk_cache.items():
        expired_chunks = []
        for chunk_index, chunk_data in chunks.items():
            if chunk_data.get('expires_at') and now > chunk_data['expires_at']:
                expired_chunks.append(chunk_index)
        
        for chunk_index in expired_chunks:
            del chunks[chunk_index]
        
        if not chunks:
            expired_codes.append(code)
    
    for code in expired_codes:
        del chunk_cache[code]
        if code in file_info_cache:
            del file_info_cache[code]
        if code in encrypted_key_cache:
            del encrypted_key_cache[code]


@router.post("/codes/{code}/upload-chunk")
async def upload_chunk(
    code: str,
    chunk_index: int = Form(...),
    chunk_data: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    上传加密的文件块（流式传输）
    
    特点：
    - 文件块在客户端加密后上传
    - 服务器只存储加密后的数据，无法查看内容
    - 数据存储在内存中，不写入磁盘
    - 支持一对多：多个接收者可以同时下载
    """
    # 验证取件码
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    # 检查取件码
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
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
    
    # 清理过期块
    cleanup_expired_chunks()
    
    # 读取加密后的数据块
    encrypted_data = await chunk_data.read()
    
    if not encrypted_data:
        return bad_request_response(msg="文件块数据为空")
    
    # 计算数据块哈希（用于验证完整性）
    chunk_hash = hashlib.sha256(encrypted_data).hexdigest()
    
    # 存储到内存缓存（不写入磁盘）
    if code not in chunk_cache:
        chunk_cache[code] = {}
    
    chunk_cache[code][chunk_index] = {
        'data': encrypted_data,
        'hash': chunk_hash,
        'created_at': datetime.utcnow(),
        'expires_at': datetime.utcnow() + timedelta(minutes=5)  # 5分钟后过期
    }
    
    return success_response(
        msg="文件块上传成功（已加密存储）",
        data={
            "chunkIndex": chunk_index,
            "chunkHash": chunk_hash,
            "expiresAt": (datetime.utcnow() + timedelta(minutes=5)).isoformat() + "Z"
        }
    )


@router.post("/codes/{code}/upload-complete")
async def upload_complete(
    code: str,
    request: UploadCompleteRequest,
    db: Session = Depends(get_db)
):
    """
    通知服务器上传完成
    
    存储文件元信息，供接收者查询
    """
    # 验证取件码
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    # 检查取件码
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
    # 存储文件信息
    file_info_cache[code] = {
        'fileName': request.fileName,
        'fileSize': request.fileSize,
        'mimeType': request.mimeType,
        'totalChunks': request.totalChunks,
        'uploadedAt': datetime.utcnow()
    }
    
    return success_response(
        msg="上传完成通知已接收",
        data={
            "code": code,
            "totalChunks": request.totalChunks,
            "fileSize": request.fileSize,
            "fileName": request.fileName
        }
    )


@router.post("/codes/{code}/store-encrypted-key")
async def store_encrypted_key(
    code: str,
    encryptedKey: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    存储加密后的文件加密密钥
    
    特点：
    - 密钥已用取件码加密，服务器无法直接获取原始密钥
    - 只有拥有取件码的用户才能解密
    - 保持端到端加密的安全性
    """
    # 验证取件码
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    # 检查取件码
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
    # 存储加密后的密钥
    encrypted_key_cache[code] = encryptedKey
    
    return success_response(
        msg="加密密钥已存储",
        data={"code": code}
    )


@router.get("/codes/{code}/encrypted-key")
async def get_encrypted_key(
    code: str,
    db: Session = Depends(get_db)
):
    """
    获取加密后的文件加密密钥
    
    接收者使用此接口获取加密密钥，然后用取件码解密
    """
    # 验证取件码
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    # 检查取件码
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
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
    
    # 获取加密后的密钥
    if code not in encrypted_key_cache:
        return not_found_response(msg="加密密钥不存在，可能尚未上传完成")
    
    encrypted_key = encrypted_key_cache[code]
    
    return success_response(data={
        "encryptedKey": encrypted_key
    })


@router.get("/codes/{code}/file-info")
async def get_file_info(
    code: str,
    db: Session = Depends(get_db)
):
    """
    获取文件信息
    
    接收者使用此接口获取文件元信息
    """
    # 验证取件码
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    # 检查取件码
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
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
    
    # 获取文件信息
    if code not in file_info_cache:
        return not_found_response(msg="文件信息不存在，可能尚未上传完成")
    
    file_info = file_info_cache[code]
    
    return success_response(data={
        "fileName": file_info['fileName'],
        "fileSize": file_info['fileSize'],
        "mimeType": file_info['mimeType'],
        "totalChunks": file_info['totalChunks'],
        "uploadedAt": file_info['uploadedAt'].isoformat() + "Z"
    })


@router.get("/codes/{code}/download-chunk/{chunk_index}")
async def download_chunk(
    code: str,
    chunk_index: int,
    db: Session = Depends(get_db)
):
    """
    下载加密的文件块（流式传输）
    
    特点：
    - 返回加密后的数据块
    - 客户端解密后重组文件
    - 支持多个接收者同时下载
    - 数据从内存读取，不涉及磁盘
    """
    # 验证取件码
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    # 检查取件码
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
    # 清理过期块
    cleanup_expired_chunks()
    
    # 从内存缓存读取
    if code not in chunk_cache or chunk_index not in chunk_cache[code]:
        return not_found_response(msg="文件块不存在或已过期")
    
    chunk_info = chunk_cache[code][chunk_index]
    
    # 检查是否过期
    if chunk_info.get('expires_at') and datetime.utcnow() > chunk_info['expires_at']:
        # 自动删除过期数据
        del chunk_cache[code][chunk_index]
        return not_found_response(msg="文件块已过期")
    
    # 返回加密后的数据块（流式响应）
    return StreamingResponse(
        io.BytesIO(chunk_info['data']),
        media_type="application/octet-stream",
        headers={
            "X-Chunk-Index": str(chunk_index),
            "X-Chunk-Hash": chunk_info['hash'],
            "X-Encrypted": "true",  # 标识数据已加密
            "Content-Disposition": f"attachment; filename=chunk_{chunk_index}.encrypted"
        }
    )


@router.post("/codes/{code}/download-complete")
async def download_complete(
    code: str,
    db: Session = Depends(get_db)
):
    """
    通知服务器下载完成
    
    可选：可以在这里更新取件码状态或清理数据
    """
    # 验证取件码
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    # 检查取件码
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
    # 注意：这里不删除文件块，因为可能还有其他接收者需要下载
    # 文件块会在过期后自动清理
    
    return success_response(msg="下载完成通知已接收")


@router.delete("/codes/{code}/chunks")
async def delete_chunks(
    code: str,
    db: Session = Depends(get_db)
):
    """
    删除所有文件块（传输完成后调用）
    
    特点：
    - 立即从内存中删除
    - 不涉及磁盘操作
    - 确保数据完全清除
    """
    # 验证取件码
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    # 检查取件码
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
    # 删除所有文件块
    if code in chunk_cache:
        del chunk_cache[code]
    
    # 删除文件信息
    if code in file_info_cache:
        del file_info_cache[code]
    
    # 删除加密密钥
    if code in encrypted_key_cache:
        del encrypted_key_cache[code]
    
    return success_response(msg="所有文件块已删除")

