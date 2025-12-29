from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime


class UserInfo(BaseModel):
    """用户信息模型（匿名）"""
    userAgent: str = Field(..., description="用户代理字符串")
    ipAddress: str = Field(..., description="IP地址")
    platform: Optional[str] = Field(None, description="平台信息")


class SenderRegisterRequest(BaseModel):
    """发送方注册请求模型"""
    senderInfo: UserInfo
    callbackUrl: Optional[HttpUrl] = Field(None, description="回调URL")


class WebRTCOfferRequest(BaseModel):
    """WebRTC Offer请求模型"""
    sessionId: str = Field(..., min_length=1, max_length=64, description="会话ID")
    offer: str = Field(..., min_length=1, description="SDP Offer字符串")
    receiverInfo: Optional[UserInfo] = Field(None, description="接收方信息")


class IceCandidate(BaseModel):
    """ICE候选模型"""
    candidate: str = Field(..., description="ICE候选字符串")
    sdpMid: Optional[str] = Field(None, description="SDP媒体标识")
    sdpMLineIndex: Optional[int] = Field(None, description="SDP媒体行索引")


class WebRTCAnswerRequest(BaseModel):
    """WebRTC Answer请求模型"""
    sessionId: str = Field(..., description="会话ID")
    answer: str = Field(..., description="SDP Answer字符串")
    iceCandidates: Optional[List[IceCandidate]] = Field(None, description="初始ICE候选")


class IceCandidateRequest(BaseModel):
    """ICE候选请求模型"""
    sessionId: str = Field(..., description="会话ID")
    candidate: IceCandidate = Field(..., description="ICE候选对象")
    role: str = Field("sender", description="发送方角色", pattern="^(sender|receiver)$")


class ReportRequest(BaseModel):
    """举报请求模型"""
    code: str = Field(..., pattern=r'^[A-Z0-9]{6}$', description="取件码")
    reason: str = Field(..., min_length=1, max_length=500, description="举报原因")
    reporterInfo: Optional[UserInfo] = Field(None, description="举报者信息")


class CreateCodeRequest(BaseModel):
    """创建取件码请求模型"""
    originalName: str = Field(..., min_length=1, max_length=255, description="文件原始名称")
    size: int = Field(..., gt=0, description="文件大小（字节）")
    mimeType: Optional[str] = Field(None, max_length=100, description="文件MIME类型")
    hash: Optional[str] = Field(None, max_length=64, description="文件SHA256哈希值")
    limitCount: Optional[int] = Field(3, ge=1, le=999, description="最大使用次数（999=无限）")
    expireHours: Optional[int] = Field(24, ge=1, le=168, description="过期时间（小时，默认24小时，最大7天）")