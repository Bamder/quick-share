from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class User(Base):
    """
    用户模型
    
    字段说明：
    - id: 用户ID（主键）
    - username: 用户名（唯一）
    - password_hash: 密码哈希值
    - created_at: 创建时间
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, comment="用户ID")
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    password_hash = Column(String(128), nullable=False, comment="密码哈希值")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
