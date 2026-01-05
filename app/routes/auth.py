from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr, Field
import hashlib
from jose import jwt

from app.utils.response import (
    success_response, created_response,
    not_found_response, bad_request_response
)
from app.extensions import get_db
from app.models.user import User
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["认证管理"], prefix="/auth")


class RegisterRequest(BaseModel):
    """注册请求模型"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=50, description="密码")


class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户响应模型"""
    id: int
    username: str
    created_at: datetime


class TokenResponse(BaseModel):
    """Token响应模型"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class VerifyTokenRequest(BaseModel):
    """验证Token请求模型"""
    token: str


class VerifyTokenResponse(BaseModel):
    """验证Token响应模型"""
    user: UserResponse


@router.post("/register", status_code=201, response_model=TokenResponse)
async def register(
    request_data: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    用户注册
    
    参数：
    - request_data: 注册信息
    - request: FastAPI请求对象
    - db: 数据库会话
    
    返回：
    - 访问令牌
    - 用户信息
    """
    # 检查用户名是否已存在
    existing_user = db.query(User).filter(User.username == request_data.username).first()
    if existing_user:
        return bad_request_response(msg="用户名已存在")
    
    # 对密码进行哈希处理
    password_hash = hashlib.sha256(request_data.password.encode()).hexdigest()
    
    # 创建新用户
    user = User(
        username=request_data.username,
        password_hash=password_hash
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # 生成访问令牌
    access_token = create_access_token(user_id=user.id)
    
    # 构建响应数据
    user_response = UserResponse(
        id=user.id,
        username=user.username,
        created_at=user.created_at
    )
    
    return created_response(
        msg="注册成功",
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_response
        }
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    用户登录
    
    参数：
    - request_data: 登录信息
    - request: FastAPI请求对象
    - db: 数据库会话
    
    返回：
    - 访问令牌
    - 用户信息
    """
    # 查找用户
    user = db.query(User).filter(User.username == request_data.username).first()
    if not user:
        return bad_request_response(msg="用户名或密码错误")
    
    # 验证密码
    password_hash = hashlib.sha256(request_data.password.encode()).hexdigest()
    if user.password_hash != password_hash:
        return bad_request_response(msg="用户名或密码错误")
    
    # 生成访问令牌
    access_token = create_access_token(user_id=user.id)
    
    # 构建响应数据
    user_response = UserResponse(
        id=user.id,
        username=user.username,
        created_at=user.created_at
    )
    
    return success_response(
        msg="登录成功",
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_response
        }
    )


@router.get("/verify")
async def verify_token(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    验证访问令牌
    
    参数：
    - request: FastAPI请求对象，包含Authorization头
    - db: 数据库会话
    
    返回：
    - 用户信息
    """
    # 从请求头获取token
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return bad_request_response(msg="缺少Authorization头")
    
    # 检查token格式
    if not auth_header.startswith("Bearer "):
        return bad_request_response(msg="Authorization头格式错误")
    
    token = auth_header.split(" ")[1]
    
    try:
        # 验证token
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        
        if not user_id:
            return bad_request_response(msg="无效的令牌")
        
        # 查找用户
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            return not_found_response(msg="用户不存在")
        
        # 构建响应数据
        user_response = UserResponse(
            id=user.id,
            username=user.username,
            created_at=user.created_at
        )
        
        return success_response(
            data={"user": user_response}
        )
    
    except jwt.ExpiredSignatureError:
        return bad_request_response(msg="令牌已过期")
    except jwt.InvalidTokenError:
        return bad_request_response(msg="无效的令牌")
    except Exception as e:
        logger.error(f"验证令牌时发生错误: {str(e)}")
        return bad_request_response(msg="验证令牌时发生错误")


def create_access_token(user_id: int) -> str:
    """
    生成访问令牌
    
    参数：
    - user_id: 用户ID
    
    返回：
    - 访问令牌字符串
    """
    # 构建payload
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow()
    }
    
    # 生成token
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return token


def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    获取当前登录用户
    
    参数：
    - request: FastAPI请求对象
    - db: 数据库会话
    
    返回：
    - 当前用户对象
    - None: 如果没有登录
    """
    # 从请求头获取token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    
    try:
        # 验证token
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        
        if not user_id:
            return None
        
        # 查找用户
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user
    
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception as e:
        logger.error(f"获取当前用户时发生错误: {str(e)}")
        return None
