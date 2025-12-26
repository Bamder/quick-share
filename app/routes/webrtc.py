from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional

from app.utils.response import (
    success_response, created_response, 
    not_found_response, bad_request_response
)
from app.utils.validation import validate_pickup_code, validate_session_id, validate_ip_address
from app.extensions import get_db
from app.schemas.request import (
    SenderRegisterRequest, WebRTCOfferRequest, 
    WebRTCAnswerRequest, IceCandidateRequest
)
from app.schemas.response import (
    SenderRegisterResponse, WebRTCOfferResponse, 
    WebRTCAnswerResponse
)
from app.models.pickup_code import PickupCode
from app.models.webrtc_session import WebRTCSession
from app.models.registered_sender import RegisteredSender

router = APIRouter(tags=["WebRTC信令"])


@router.post("/codes/{code}/webrtc/sender/register")
async def register_sender(
    code: str, 
    request: SenderRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    发送方(Sender)注册
    
    发送方向信令服务器注册，准备接收Offer
    """
    # 验证取件码
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    # 验证IP地址
    if not validate_ip_address(request.senderInfo.ipAddress):
        return bad_request_response(msg="IP地址格式错误")
    
    # 检查取件码是否存在
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
    # 检查取件码状态
    if pickup_code.status in ["completed", "expired"]:
        return bad_request_response(msg=f"取件码状态为 {pickup_code.status}，不可用")
    
    # 创建注册记录
    registered_sender = RegisteredSender(
        code=code,
        sender_info=request.senderInfo.dict(),
        callback_url=str(request.callbackUrl) if request.callbackUrl else None,
        status="waiting",
        expires_at=datetime.utcnow() + timedelta(minutes=5)
    )
    
    db.add(registered_sender)
    db.commit()
    db.refresh(registered_sender)
    
    # 构建响应
    response_data = SenderRegisterResponse(
        registeredAt=registered_sender.created_at,
        expiresIn=300,
        expiresAt=registered_sender.expires_at
    )
    
    return created_response(
        msg="Sender注册成功，等待Offer",
        data=response_data
    )


@router.post("/codes/{code}/webrtc/offer")
async def create_webrtc_offer(
    code: str,
    request: WebRTCOfferRequest,
    db: Session = Depends(get_db)
):
    """
    接收方(Receiver)创建WebRTC Offer
    """
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    if not validate_session_id(request.sessionId):
        return bad_request_response(msg="会话ID格式错误")
    
    # 检查取件码
    pickup_code = db.query(PickupCode).filter(PickupCode.code == code).first()
    if not pickup_code:
        return not_found_response(msg=f"取件码 {code} 不存在")
    
    # 检查取件码状态
    if pickup_code.status in ["completed", "expired"]:
        return bad_request_response(msg=f"取件码状态为 {pickup_code.status}，不可用")
    
    # 创建或更新WebRTC会话
    webrtc_session = db.query(WebRTCSession).filter(
        WebRTCSession.code == code,
        WebRTCSession.session_id == request.sessionId
    ).first()
    
    if webrtc_session:
        # 更新现有会话
        webrtc_session.offer = request.offer
        webrtc_session.status = "offer_created"
        webrtc_session.ice_candidates = None  # 清空之前的ICE候选
    else:
        # 创建新会话
        webrtc_session = WebRTCSession(
            code=code,
            session_id=request.sessionId,
            offer=request.offer,
            status="offer_created"
        )
        db.add(webrtc_session)
    
    db.commit()
    db.refresh(webrtc_session)
    
    # 检查是否有已注册的Sender
    registered_sender = db.query(RegisteredSender).filter(
        RegisteredSender.code == code,
        RegisteredSender.status == "waiting"
    ).first()
    
    sender_found = registered_sender is not None
    if sender_found and registered_sender:
        # 更新Sender状态为已通知
        registered_sender.status = "notified"
        registered_sender.session_id = request.sessionId
        db.commit()
    
    # 构建响应
    response_data = {
        "sessionId": webrtc_session.session_id,
        "status": webrtc_session.status,
        "createdAt": webrtc_session.created_at,
        "senderFound": sender_found,
        "expiresIn": 300
    }
    
    return created_response(
        msg="WebRTC Offer创建成功",
        data=response_data
    )


@router.get("/codes/{code}/webrtc/offer/{session_id}")
async def get_webrtc_offer(
    code: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    发送方(Sender)获取WebRTC Offer
    """
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    if not validate_session_id(session_id):
        return bad_request_response(msg="会话ID格式错误")
    
    # 查询WebRTC会话
    webrtc_session = db.query(WebRTCSession).filter(
        WebRTCSession.code == code,
        WebRTCSession.session_id == session_id,
        WebRTCSession.status.in_(["offer_created", "answer_received", "connected"])
    ).first()
    
    if not webrtc_session:
        return not_found_response(msg="WebRTC Offer不存在或已过期")
    
    # 构建响应
    response_data = WebRTCOfferResponse(
        sessionId=webrtc_session.session_id,
        offer=webrtc_session.offer or "",
        status=webrtc_session.status,
        createdAt=webrtc_session.created_at
    )
    
    return success_response(data=response_data)


@router.post("/codes/{code}/webrtc/answer")
async def submit_webrtc_answer(
    code: str,
    request: WebRTCAnswerRequest,
    db: Session = Depends(get_db)
):
    """
    发送方(Sender)提交WebRTC Answer
    """
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    if not validate_session_id(request.sessionId):
        return bad_request_response(msg="会话ID格式错误")
    
    # 查找对应的WebRTC会话
    webrtc_session = db.query(WebRTCSession).filter(
        WebRTCSession.code == code,
        WebRTCSession.session_id == request.sessionId,
        WebRTCSession.status == "offer_created"
    ).first()
    
    if not webrtc_session:
        return not_found_response(msg="对应的WebRTC Offer不存在或已过期")
    
    # 更新会话
    webrtc_session.answer = request.answer
    webrtc_session.status = "answer_received"
    
    # 如果有ICE候选，存储它们
    if request.iceCandidates:
        webrtc_session.ice_candidates = [
            candidate.dict() for candidate in request.iceCandidates
        ]
    
    db.commit()
    db.refresh(webrtc_session)
    
    # 构建响应
    response_data = WebRTCAnswerResponse(
        sessionId=webrtc_session.session_id,
        answer=webrtc_session.answer or "",
        status=webrtc_session.status,
        createdAt=webrtc_session.updated_at or datetime.utcnow()
    )
    
    return success_response(
        msg="WebRTC Answer提交成功",
        data=response_data
    )


@router.get("/codes/{code}/webrtc/answer/{session_id}")
async def get_webrtc_answer(
    code: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    接收方(Receiver)获取WebRTC Answer
    """
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    if not validate_session_id(session_id):
        return bad_request_response(msg="会话ID格式错误")
    
    # 查询WebRTC会话
    webrtc_session = db.query(WebRTCSession).filter(
        WebRTCSession.code == code,
        WebRTCSession.session_id == session_id,
        WebRTCSession.status.in_(["answer_received", "connected"])
    ).first()
    
    if not webrtc_session:
        # 检查是否还在等待Answer
        pending_session = db.query(WebRTCSession).filter(
            WebRTCSession.code == code,
            WebRTCSession.session_id == session_id,
            WebRTCSession.status == "offer_created"
        ).first()
        
        if pending_session:
            return not_found_response(
                msg="WebRTC Answer尚未创建",
                data={
                    "status": "waiting",
                    "message": "等待Sender创建Answer",
                    "lastChecked": datetime.utcnow().isoformat() + "Z"
                }
            )
        else:
            return not_found_response(msg="WebRTC会话不存在")
    
    # 构建响应
    response_data = WebRTCAnswerResponse(
        sessionId=webrtc_session.session_id,
        answer=webrtc_session.answer or "",
        status=webrtc_session.status,
        createdAt=webrtc_session.updated_at or webrtc_session.created_at
    )
    
    # 如果有ICE候选，也返回
    if webrtc_session.ice_candidates:
        response_data_dict = response_data.dict()
        response_data_dict["iceCandidates"] = webrtc_session.ice_candidates
        return success_response(data=response_data_dict)
    
    return success_response(data=response_data)


@router.post("/codes/{code}/webrtc/ice-candidate")
async def send_ice_candidate(
    code: str,
    request: IceCandidateRequest,
    db: Session = Depends(get_db)
):
    """
    发送ICE候选
    
    支持双向ICE候选交换：
    - Sender发送给Receiver
    - Receiver发送给Sender
    """
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    if not validate_session_id(request.sessionId):
        return bad_request_response(msg="会话ID格式错误")
    
    # 查找WebRTC会话
    webrtc_session = db.query(WebRTCSession).filter(
        WebRTCSession.code == code,
        WebRTCSession.session_id == request.sessionId
    ).first()
    
    if not webrtc_session:
        return not_found_response(msg="WebRTC会话不存在")
    
    # 更新ICE候选列表
    current_candidates = webrtc_session.ice_candidates or []
    
    # 添加新候选
    new_candidate = {
        **request.candidate.dict(),
        "role": request.role,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    current_candidates.append(new_candidate)
    webrtc_session.ice_candidates = current_candidates
    
    # 如果是第一个ICE候选，更新状态
    if webrtc_session.status == "answer_received" and len(current_candidates) > 0:
        webrtc_session.status = "connected"
    
    db.commit()
    
    # 构建响应
    return success_response(
        msg="ICE候选接收成功",
        data={
            "sessionId": webrtc_session.session_id,
            "candidateCount": len(current_candidates),
            "receivedAt": datetime.utcnow().isoformat() + "Z",
            "role": request.role
        }
    )


@router.get("/codes/{code}/webrtc/ice-candidates/{session_id}")
async def get_ice_candidates(
    code: str,
    session_id: str,
    role: Optional[str] = None,
    since: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取ICE候选列表
    
    参数：
    - role: 过滤特定角色的候选 (sender/receiver)
    - since: 只返回此时间戳之后的候选
    """
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    if not validate_session_id(session_id):
        return bad_request_response(msg="会话ID格式错误")
    
    # 查找WebRTC会话
    webrtc_session = db.query(WebRTCSession).filter(
        WebRTCSession.code == code,
        WebRTCSession.session_id == session_id
    ).first()
    
    if not webrtc_session:
        return not_found_response(msg="WebRTC会话不存在")
    
    # 获取ICE候选
    all_candidates = webrtc_session.ice_candidates or []
    
    # 过滤
    filtered_candidates = all_candidates
    
    if role:
        filtered_candidates = [
            c for c in filtered_candidates 
            if c.get("role") == role
        ]
    
    if since:
        try:
            since_time = datetime.fromisoformat(since.replace('Z', '+00:00'))
            filtered_candidates = [
                c for c in filtered_candidates
                if datetime.fromisoformat(c.get("timestamp", "").replace('Z', '+00:00')) > since_time
            ]
        except:
            pass  # 如果时间格式错误，忽略过滤
    
    # 构建响应
    return success_response(data={
        "sessionId": webrtc_session.session_id,
        "candidates": filtered_candidates,
        "totalCount": len(all_candidates),
        "filteredCount": len(filtered_candidates),
        "lastUpdated": webrtc_session.updated_at.isoformat() + "Z" if webrtc_session.updated_at else None
    })


@router.get("/codes/{code}/webrtc/session/{session_id}/status")
async def get_session_status(
    code: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    获取WebRTC会话状态
    """
    if not validate_pickup_code(code):
        return bad_request_response(msg="取件码格式错误")
    
    if not validate_session_id(session_id):
        return bad_request_response(msg="会话ID格式错误")
    
    # 查找WebRTC会话
    webrtc_session = db.query(WebRTCSession).filter(
        WebRTCSession.code == code,
        WebRTCSession.session_id == session_id
    ).first()
    
    if not webrtc_session:
        return not_found_response(msg="WebRTC会话不存在")
    
    # 计算过期时间（创建后5分钟）
    expires_at = webrtc_session.created_at + timedelta(minutes=5)
    is_expired = datetime.utcnow() > expires_at
    
    if is_expired and webrtc_session.status not in ["completed", "failed", "closed"]:
        webrtc_session.status = "expired"
        db.commit()
    
    # 构建响应
    return success_response(data={
        "sessionId": webrtc_session.session_id,
        "status": webrtc_session.status,
        "createdAt": webrtc_session.created_at.isoformat() + "Z",
        "updatedAt": webrtc_session.updated_at.isoformat() + "Z" if webrtc_session.updated_at else None,
        "expiresAt": expires_at.isoformat() + "Z",
        "isExpired": is_expired,
        "hasOffer": webrtc_session.offer is not None,
        "hasAnswer": webrtc_session.answer is not None,
        "iceCandidateCount": len(webrtc_session.ice_candidates or [])
    })