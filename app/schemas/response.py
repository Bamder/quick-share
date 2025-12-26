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


class WebRTCOfferResponse(BaseModel):
    """WebRTC Offer响应模型"""
    sessionId: str
    offer: str
    status: str
    createdAt: datetime


class WebRTCAnswerResponse(BaseModel):
    """WebRTC Answer响应模型"""
    sessionId: str
    answer: str
    status: str
    createdAt: datetime


class SenderRegisterResponse(BaseModel):
    """发送方注册响应模型"""
    registeredAt: datetime
    expiresIn: int
    expiresAt: datetime


class UsageUpdateResponse(BaseModel):
    """使用次数更新响应模型"""
    code: str
    usedCount: int
    limitCount: int
    remaining: int
    updatedAt: datetime


class IceCandidateResponse(BaseModel):
    """ICE候选响应模型"""
    candidate: str
    sdpMid: Optional[str] = None
    sdpMLineIndex: Optional[int] = None
    createdAt: datetime