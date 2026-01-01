from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class FileInfoResponse(BaseModel):
    """文件信息响应模型"""
    fileId: int
    originalName: str
    storedName: str
    size: int
    hash: Optional[str] = None
    mimeType: Optional[str] = None
    createdAt: datetime


class PickupCodeStatusResponse(BaseModel):
    """取件码状态响应模型"""
    code: str
    fileId: int
    fileName: str
    fileSize: int
    mimeType: str
    status: str
    usedCount: int
    limitCount: int
    expireAt: datetime
    createdAt: datetime


class UsageUpdateResponse(BaseModel):
    """使用次数更新响应模型"""
    code: str
    usedCount: int
    limitCount: int
    remaining: int
    updatedAt: datetime


class CreateCodeResponse(BaseModel):
    """创建取件码响应模型"""
    code: str
    fileId: int
    fileName: str
    fileSize: int
    mimeType: Optional[str] = None
    limitCount: int
    expireAt: datetime
    createdAt: datetime