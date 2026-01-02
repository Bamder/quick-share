"""
服务器中转模式API
使用端到端加密，服务器无法查看文件内容
"""

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Body, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
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
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["服务器中转"], prefix="/relay")


def get_pickup_code_by_lookup(db: Session, lookup_code: str) -> Optional[PickupCode]:
    """
    使用查找码（6位）查询取件码
    
    参数：
    - db: 数据库会话
    - lookup_code: 6位查找码（服务器只接收查找码，不接触密钥码）
    
    返回：
    - PickupCode对象，如果找到
    - None，如果未找到
    
    安全性：
    - 服务器只接收和查询6位查找码
    - 后6位密钥码完全不进入服务器
    """
    # 直接使用6位查找码查询数据库
    pickup_code = db.query(PickupCode).filter(
        PickupCode.code == lookup_code
    ).first()
    
    return pickup_code


class UploadCompleteRequest(BaseModel):
    """上传完成请求模型"""
    totalChunks: int
    fileSize: int
    fileName: str
    mimeType: str


# 临时内存存储（生产环境应使用Redis）
# 格式: {lookup_code: {chunk_index: {data: bytes, hash: str, created_at: datetime, expires_at: datetime}}}
# 注意：使用前6位查找码作为键，服务器不需要知道后6位密钥码
chunk_cache = {}

# 文件信息缓存（格式: {lookup_code: {fileName, fileSize, mimeType, totalChunks, uploadedAt}}）
file_info_cache = {}

# 加密密钥缓存（格式: {lookup_code: encryptedKeyBase64}）
# 
# ============================================================================
# 密钥概念体系（4个密钥相关概念及其关系）
# ============================================================================
# 
# 1. 文件加密密钥（原始密钥 / File Encryption Key）
#    - 类型：CryptoKey（AES-GCM，256位）
#    - 生成方式：随机生成（客户端）
#    - 用途：直接加密/解密文件块
#    - 存储位置：客户端浏览器缓存（以文件哈希为键）
#    - 是否传输到服务器：否（只传输加密后的版本）
# 
# 2. 密钥码（6位密钥码 / Key Code）
#    - 类型：字符串（6位大写字母+数字）
#    - 来源：取件码的后6位（如 "ABC123DEF456" 中的 "DEF456"）
#    - 用途：作为材料派生密钥，用于加密/解密文件加密密钥
#    - 是否传输到服务器：否（服务器只接收前6位查找码）
# 
# 3. 派生密钥（Derived Key）
#    - 类型：CryptoKey（AES-GCM，256位）
#    - 生成方式：从密钥码通过PBKDF2派生（100000次迭代，SHA-256）
#    - 用途：加密/解密文件加密密钥（原始密钥）
#    - 存储位置：不存储，每次使用时临时派生（客户端）
#    - 是否传输到服务器：否（只在客户端使用）
# 
# 4. 加密后的文件加密密钥（Encrypted File Encryption Key）
#    - 类型：字符串（Base64编码）
#    - 生成方式：用派生密钥加密文件加密密钥（原始密钥）
#    - 用途：安全存储到服务器，供接收者下载
#    - 存储位置：服务器内存缓存（本变量 encrypted_key_cache）
#    - 是否传输到服务器：是（这是唯一传输到服务器的密钥相关数据）
# 
# ============================================================================
# 密钥关系链（加密流程）
# ============================================================================
# 
# 取件码（12位）
# ├── 查找码（前6位）→ 用于服务器查询和缓存键
# └── 密钥码（后6位）→ 派生密钥 → 加密 → 文件加密密钥（原始密钥）→ 加密文件块
# 
# 详细流程：
# 1. Sender生成文件加密密钥（原始密钥）→ 随机生成，256位AES-GCM
# 2. Sender提取密钥码（后6位）→ 从取件码提取
# 3. Sender派生密钥 → 从密钥码通过PBKDF2派生256位AES-GCM密钥
# 4. Sender加密文件加密密钥 → 用派生密钥加密原始密钥
# 5. Sender存储到服务器 → 只存储加密后的密钥（Base64编码）← 存储在此缓存中
# 6. Receiver从服务器获取 → 获取加密后的密钥（从本缓存获取）
# 7. Receiver派生密钥 → 从密钥码通过PBKDF2派生相同的密钥
# 8. Receiver解密文件加密密钥 → 用派生密钥解密，得到原始密钥
# 9. Receiver解密文件块 → 用原始密钥解密文件块
# 
# ============================================================================
# 服务器可见性
# ============================================================================
# 
# 服务器可以看到（本缓存存储的内容）：
# - 查找码（前6位）：用于查询和缓存键
# - 加密后的文件加密密钥：Base64编码的加密数据（本缓存的值）
# - 加密后的文件块：加密后的文件数据
# 
# 服务器无法看到：
# - 密钥码（后6位）：不传输到服务器
# - 派生密钥：只在客户端生成和使用
# - 文件加密密钥（原始密钥）：不传输到服务器
# - 文件内容：已加密，无法解密
# 
# 因此，即使服务器被完全攻破，攻击者也无法：
# - 解密文件内容（缺少密钥码和原始密钥）
# - 获取原始密钥（缺少密钥码来派生密钥）
# - 解密文件块（缺少原始密钥）
encrypted_key_cache = {}

# 查找码映射表（格式: {new_lookup_code: original_lookup_code}）
# 用于支持一个文件对应多个取件码，复用文件块缓存
# 当创建新取件码复用旧文件时，新 lookup_code 映射到原始的 lookup_code
lookup_code_mapping = {}


def get_original_lookup_code(lookup_code: str) -> str:
    """
    获取原始的查找码（如果存在映射，返回映射的原始码；否则创建自映射并返回自身）
    
    参数:
    - lookup_code: 当前查找码（6位）
    
    返回:
    - 原始的查找码（6位）
    """
    if lookup_code not in lookup_code_mapping:
        # 如果映射表中不存在，创建自映射（键值相同）
        lookup_code_mapping[lookup_code] = lookup_code
    return lookup_code_mapping[lookup_code]


def cleanup_expired_chunks():
    """清理过期的文件块"""
    now = datetime.utcnow()
    expired_lookup_codes = []
    
    # 遍历所有查找码（前6位）
    for lookup_code, chunks in chunk_cache.items():
        expired_chunks = []
        for chunk_index, chunk_data in chunks.items():
            if chunk_data.get('expires_at') and now > chunk_data['expires_at']:
                expired_chunks.append(chunk_index)
        
        for chunk_index in expired_chunks:
            del chunks[chunk_index]
        
        if not chunks:
            expired_lookup_codes.append(lookup_code)
    
    # 清理所有过期的查找码相关数据
    for lookup_code in expired_lookup_codes:
        del chunk_cache[lookup_code]
        if lookup_code in file_info_cache:
            del file_info_cache[lookup_code]
        if lookup_code in encrypted_key_cache:
            del encrypted_key_cache[lookup_code]


@router.post("/codes/{code}/upload-chunk")
async def upload_chunk(
    code: str,
    chunk_data: UploadFile = File(...),
    chunk_index: Optional[int] = Form(None),
    chunk_index_query: Optional[int] = Query(None, alias="chunk_index"),
    db: Session = Depends(get_db)
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
    
    # 清理过期块
    cleanup_expired_chunks()
    
    # code 就是查找码（6位），直接用作缓存键
    lookup_code = code
    
    # 检查是否存在映射，如果存在则使用原始的 lookup_code 访问缓存
    original_lookup_code = get_original_lookup_code(lookup_code)
    
    # 读取加密后的数据块
    encrypted_data = await chunk_data.read()
    
    if not encrypted_data:
        return bad_request_response(msg="文件块数据为空")
    
    # 计算数据块哈希（用于验证完整性）
    chunk_hash = hashlib.sha256(encrypted_data).hexdigest()
    
    # 检查文件块是否已存在（通过映射表，可能已有缓存）
    # 如果已存在且未过期，直接返回成功，不重复存储
    if original_lookup_code in chunk_cache:
        if chunk_index in chunk_cache[original_lookup_code]:
            existing_chunk = chunk_cache[original_lookup_code][chunk_index]
            # 检查是否过期
            if existing_chunk.get('expires_at') and datetime.utcnow() < existing_chunk['expires_at']:
                # 文件块已存在且未过期，直接返回成功（复用现有块）
                logger.info(f"文件块 {chunk_index} 已存在（通过映射表复用），跳过上传")
                return success_response(
                    msg="文件块已存在（复用），无需重复上传",
                    data={
                        "chunkIndex": chunk_index,
                        "chunkHash": existing_chunk['hash'],
                        "reused": True,  # 标记为复用
                        "expiresAt": existing_chunk['expires_at'].isoformat() + "Z"
                    }
                )
    
    # 存储到内存缓存（不写入磁盘）
    # 使用原始的查找码作为键，支持多个 lookup_code 共享同一个文件块缓存
    if original_lookup_code not in chunk_cache:
        chunk_cache[original_lookup_code] = {}
    
    chunk_cache[original_lookup_code][chunk_index] = {
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
    
    # 检查是否存在映射，如果存在则使用原始的 lookup_code 访问缓存
    original_lookup_code = get_original_lookup_code(lookup_code)
    
    # 存储文件信息
    # 使用原始的查找码作为键，支持多个 lookup_code 共享同一个文件信息缓存
    file_info_cache[original_lookup_code] = {
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
    
    重要概念区分：
    1. 文件加密密钥（原始密钥）：
       - 随机生成的AES-GCM密钥（256位），用于直接加密/解密文件块
       - 客户端生成，不直接发送到服务器
    
    2. 密钥码（6位密钥码）：
       - 取件码的后6位，用于派生密钥来加密/解密文件加密密钥
       - 服务器不接触密钥码，只接收前6位查找码
    
    3. 此接口存储的内容：
       - 用取件码的密钥码派生密钥加密后的文件加密密钥（Base64编码）
       - 服务器无法直接获取原始的文件加密密钥
       - 只有拥有完整取件码的用户才能解密
    
    特点：
    - 密钥已用取件码的密钥码派生密钥加密，服务器无法直接获取原始密钥
    - 只有拥有完整取件码（包括后6位密钥码）的用户才能解密
    - 保持端到端加密的安全性
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
    
    # 提取查找码（前6位）用于缓存键
    # code 就是查找码（6位），直接用作缓存键
    lookup_code = code
    
    # 检查是否存在映射，如果存在则使用原始的 lookup_code 访问缓存
    original_lookup_code = get_original_lookup_code(lookup_code)
    
    # 存储加密后的密钥
    # 使用原始的查找码作为键，支持多个 lookup_code 共享同一个加密密钥缓存
    encrypted_key_cache[original_lookup_code] = encryptedKey
    logger.info(f"加密密钥已存储: lookup_code={lookup_code}, original_lookup_code={original_lookup_code}, key_length={len(encryptedKey)}")
    
    return success_response(
        msg="加密密钥已存储",
        data={"code": code, "originalLookupCode": original_lookup_code}
    )


@router.get("/codes/{code}/encrypted-key")
async def get_encrypted_key(
    code: str,
    db: Session = Depends(get_db)
):
    """
    获取加密后的文件加密密钥
    
    重要概念区分：
    1. 文件加密密钥（原始密钥）：
       - 随机生成的AES-GCM密钥（256位），用于直接加密/解密文件块
       - 客户端生成，不直接发送到服务器
    
    2. 密钥码（6位密钥码）：
       - 取件码的后6位，用于派生密钥来加密/解密文件加密密钥
       - 服务器不接触密钥码，只接收前6位查找码
    
    3. 此接口返回的内容：
       - 用取件码的密钥码派生密钥加密后的文件加密密钥（Base64编码）
       - 接收者需要使用完整取件码（包括后6位密钥码）来解密
    
    接收者使用此接口获取加密后的文件加密密钥，然后用取件码的密钥码派生密钥解密
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
    
    if pickup_code.status == "completed":
        return bad_request_response(
            msg="取件码已完成，无法使用",
            data={"code": "COMPLETED", "status": "completed"}
        )
    
    # 提取查找码（前6位）用于缓存键
    # code 就是查找码（6位），直接用作缓存键
    lookup_code = code
    
    # 检查是否存在映射，如果存在则使用原始的 lookup_code 访问缓存
    original_lookup_code = get_original_lookup_code(lookup_code)
    
    # 获取加密后的密钥
    # 使用原始的查找码作为键，支持多个 lookup_code 共享同一个加密密钥缓存
    logger.info(f"查找加密密钥: lookup_code={lookup_code}, original_lookup_code={original_lookup_code}")
    logger.info(f"加密密钥缓存键: {list(encrypted_key_cache.keys())}")
    
    if original_lookup_code not in encrypted_key_cache:
        logger.warning(f"加密密钥不存在: original_lookup_code={original_lookup_code}, 缓存键={list(encrypted_key_cache.keys())}")
        return not_found_response(msg="加密密钥不存在，可能尚未上传完成")
    
    encrypted_key = encrypted_key_cache[original_lookup_code]
    logger.info(f"✓ 找到加密密钥: lookup_code={lookup_code}, key_length={len(encrypted_key)}")
    
    return success_response(data={
        "encryptedKey": encrypted_key
    })


@router.get("/codes/{code}/check-chunks")
async def check_chunks(
    code: str,
    total_chunks: int = Query(..., description="总块数"),
    db: Session = Depends(get_db)
):
    """
    检查文件块是否已存在（用于复用旧文件块，避免重复上传）
    
    发送者使用此接口在上传前检查文件块是否已存在
    如果已存在，可以跳过上传，直接复用
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
    
    # 提取查找码（前6位）用于缓存键
    lookup_code = code
    
    # 检查是否存在映射，如果存在则使用原始的 lookup_code 访问缓存
    original_lookup_code = get_original_lookup_code(lookup_code)
    
    # 检查文件块是否存在
    existing_chunks = []
    missing_chunks = []
    
    if original_lookup_code in chunk_cache:
        for i in range(total_chunks):
            if i in chunk_cache[original_lookup_code]:
                chunk = chunk_cache[original_lookup_code][i]
                # 检查是否过期
                if chunk.get('expires_at') and datetime.utcnow() < chunk['expires_at']:
                    existing_chunks.append(i)
                else:
                    missing_chunks.append(i)
            else:
                missing_chunks.append(i)
    else:
        # 缓存不存在，所有块都需要上传
        missing_chunks = list(range(total_chunks))
    
    return success_response(
        msg="文件块检查完成",
        data={
            "existingChunks": existing_chunks,
            "missingChunks": missing_chunks,
            "totalChunks": total_chunks,
            "allExist": len(missing_chunks) == 0
        }
    )


@router.get("/codes/{code}/file-info")
async def get_file_info(
    code: str,
    db: Session = Depends(get_db)
):
    """
    获取文件信息
    
    接收者使用此接口获取文件元信息
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
    
    if pickup_code.status == "completed":
        return bad_request_response(
            msg="取件码已完成，无法使用",
            data={"code": "COMPLETED", "status": "completed"}
        )
    
    # 提取查找码（前6位）用于缓存键
    # code 就是查找码（6位），直接用作缓存键
    lookup_code = code
    
    # 检查是否存在映射，如果存在则使用原始的 lookup_code 访问缓存
    original_lookup_code = get_original_lookup_code(lookup_code)
    
    # 获取文件信息
    # 使用原始的查找码作为键，支持多个 lookup_code 共享同一个文件信息缓存
    if original_lookup_code not in file_info_cache:
        return not_found_response(msg="文件信息不存在，可能尚未上传完成")
    
    file_info = file_info_cache[original_lookup_code]
    
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
    # 验证取件码（服务器只接收6位查找码）
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误，必须为6位大写字母或数字")
    
    # 使用查找码查询取件码（服务器只接收6位查找码，不接触后6位密钥码）
    pickup_code = get_pickup_code_by_lookup(db, code)
    if not pickup_code:
        return not_found_response(msg=f"取件码不存在")
    
    # 清理过期块
    cleanup_expired_chunks()
    
    # 提取查找码（前6位）用于缓存键
    # code 就是查找码（6位），直接用作缓存键
    lookup_code = code
    
    # 检查是否存在映射，如果存在则使用原始的 lookup_code 访问缓存
    original_lookup_code = get_original_lookup_code(lookup_code)
    
    # 从内存缓存读取
    # 使用原始的查找码作为键，支持多个 lookup_code 共享同一个文件块缓存
    if original_lookup_code not in chunk_cache or chunk_index not in chunk_cache[original_lookup_code]:
        return not_found_response(msg="文件块不存在或已过期")
    
    chunk_info = chunk_cache[original_lookup_code][chunk_index]
    
    # 检查是否过期
    if chunk_info.get('expires_at') and datetime.utcnow() > chunk_info['expires_at']:
        # 自动删除过期数据
        del chunk_cache[original_lookup_code][chunk_index]
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
    # 验证取件码（服务器只接收6位查找码）
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误，必须为6位大写字母或数字")
    
    # 使用查找码查询取件码（服务器只接收6位查找码，不接触后6位密钥码）
    pickup_code = get_pickup_code_by_lookup(db, code)
    if not pickup_code:
        return not_found_response(msg=f"取件码不存在")
    
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
    
    # 删除所有文件块
    # 使用查找码（前6位）作为键，服务器不需要知道后6位密钥码
    if lookup_code in chunk_cache:
        del chunk_cache[lookup_code]
    
    # 删除文件信息
    if lookup_code in file_info_cache:
        del file_info_cache[lookup_code]
    
    # 删除加密密钥
    if lookup_code in encrypted_key_cache:
        del encrypted_key_cache[lookup_code]
    
    return success_response(msg="所有文件块已删除")

